"""Train the xG logistic regression model and evaluate it on held-out matches.

Run from the backend/ directory (after scripts.build_shots_dataset):

    python -m scripts.train_model

Outputs, in artifacts/:

    model.joblib            fitted pipeline: raw (x, y, body_part) -> P(goal)
    metrics.json            held-out metrics and split details
    evaluation_report.txt   plain-language explanation of those metrics

The split is by match_id, so no match contributes shots to both sets. The
script stops with an error instead of producing a misleading evaluation if the
data is too small for that split.
"""

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.xg_features import (  # noqa: E402
    CATEGORICAL_FEATURES,
    INPUT_COLUMNS,
    NUMERIC_FEATURES,
    add_geometry_features,
    to_model_input,
)

SHOTS_CSV = BACKEND_DIR / "data" / "processed" / "shots.csv"
ARTIFACTS_DIR = BACKEND_DIR / "artifacts"

RANDOM_SEED = 42
TEST_SIZE = 0.25  # fraction of matches held out

# Minimums below which a match-based evaluation would not mean much.
MIN_MATCHES = 10
MIN_GOALS = 50
MIN_NON_GOALS = 50
MIN_TEST_MATCHES = 3
MIN_TEST_GOALS = 10


class InsufficientDataError(RuntimeError):
    pass


def build_pipeline() -> Pipeline:
    numeric = Pipeline([
        # x/y are required inputs and the training data has no gaps; the
        # median imputer only guards against a NaN reaching the model.
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        # A missing body part becomes "Unknown", which the encoder (like any
        # unseen category) maps to all zeros, i.e. the baseline.
        ("impute", SimpleImputer(strategy="constant", fill_value="Unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    preprocess = ColumnTransformer([
        ("numeric", numeric, NUMERIC_FEATURES),
        ("categorical", categorical, CATEGORICAL_FEATURES),
    ])
    return Pipeline([
        ("geometry", FunctionTransformer(add_geometry_features)),
        ("preprocess", preprocess),
        # No class re-weighting: xG must be a calibrated probability, and
        # class_weight="balanced" would inflate every prediction toward 0.5.
        # Imbalance is handled by evaluating with log loss / Brier / ROC-AUC
        # rather than accuracy. lbfgs on scaled features with a high
        # max_iter converges reliably; a convergence warning is an error.
        ("model", LogisticRegression(C=1.0, max_iter=1000, random_state=RANDOM_SEED)),
    ])


def check_dataset(shots: pd.DataFrame) -> None:
    required = set(INPUT_COLUMNS) | {"match_id", "goal"}
    missing = required - set(shots.columns)
    if missing:
        raise InsufficientDataError(f"shots.csv is missing columns: {sorted(missing)}")
    if not shots["goal"].isin([0, 1]).all():
        raise InsufficientDataError("goal column must contain only 0 and 1")

    n_matches = shots["match_id"].nunique()
    n_goals = int(shots["goal"].sum())
    n_non_goals = int((shots["goal"] == 0).sum())
    problems = []
    if n_matches < MIN_MATCHES:
        problems.append(f"{n_matches} matches (need >= {MIN_MATCHES})")
    if n_goals < MIN_GOALS:
        problems.append(f"{n_goals} goals (need >= {MIN_GOALS})")
    if n_non_goals < MIN_NON_GOALS:
        problems.append(f"{n_non_goals} non-goals (need >= {MIN_NON_GOALS})")
    if problems:
        raise InsufficientDataError("Not enough data for a match-based split: " + "; ".join(problems))


def split_by_match(shots: pd.DataFrame):
    splitter = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=RANDOM_SEED)
    train_idx, test_idx = next(splitter.split(shots, shots["goal"], groups=shots["match_id"]))
    train, test = shots.iloc[train_idx], shots.iloc[test_idx]

    overlap = set(train["match_id"]) & set(test["match_id"])
    assert not overlap, f"Matches in both splits: {overlap}"

    test_matches = test["match_id"].nunique()
    test_goals = int(test["goal"].sum())
    if test_matches < MIN_TEST_MATCHES or test_goals < MIN_TEST_GOALS:
        raise InsufficientDataError(
            f"Held-out split too small: {test_matches} matches, {test_goals} goals "
            f"(need >= {MIN_TEST_MATCHES} matches and >= {MIN_TEST_GOALS} goals)"
        )
    if train["goal"].nunique() < 2:
        raise InsufficientDataError("Training split contains only one class")
    return train, test


def split_summary(frame: pd.DataFrame) -> dict:
    return {
        "matches": int(frame["match_id"].nunique()),
        "shots": len(frame),
        "goals": int(frame["goal"].sum()),
        "non_goals": int((frame["goal"] == 0).sum()),
        "goal_rate": round(float(frame["goal"].mean()), 4),
    }


def score(y_true: np.ndarray, p: np.ndarray) -> dict:
    p = np.clip(p, 1e-15, 1 - 1e-15)
    result = {
        "log_loss": float(log_loss(y_true, p, labels=[0, 1])),
        "brier_score": float(brier_score_loss(y_true, p)),
        "roc_auc": float(roc_auc_score(y_true, p)) if len(np.unique(y_true)) == 2 else None,
        "mean_predicted": float(p.mean()),
    }
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in result.items()}


def train_and_evaluate() -> dict:
    shots = pd.read_csv(SHOTS_CSV)
    check_dataset(shots)
    train, test = split_by_match(shots)

    pipeline = build_pipeline()
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        pipeline.fit(to_model_input(train), train["goal"])

    y_test = test["goal"].to_numpy()
    p_model = pipeline.predict_proba(to_model_input(test))[:, 1]
    p_base_rate = np.full(len(test), train["goal"].mean())

    metrics = {
        "model": "LogisticRegression",
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "input_columns": INPUT_COLUMNS,
        "features": NUMERIC_FEATURES + CATEGORICAL_FEATURES,
        "split": {
            "method": "GroupShuffleSplit by match_id",
            "test_size_fraction_of_matches": TEST_SIZE,
            "random_seed": RANDOM_SEED,
            "train": split_summary(train),
            "test": split_summary(test),
            "test_match_ids": sorted(int(m) for m in test["match_id"].unique()),
        },
        "test_metrics": {
            "model": score(y_test, p_model),
            # Reference points on the same held-out shots, not models we train:
            "baseline_training_goal_rate": score(y_test, p_base_rate),
            "statsbomb_xg_benchmark": score(y_test, test["statsbomb_xg"].to_numpy()),
        },
        "coefficients": dict(zip(
            pipeline.named_steps["preprocess"].get_feature_names_out(),
            (round(float(c), 4) for c in pipeline.named_steps["model"].coef_[0]),
        )),
        "observed_test_goal_rate": round(float(y_test.mean()), 4),
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, ARTIFACTS_DIR / "model.joblib")
    with open(ARTIFACTS_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    (ARTIFACTS_DIR / "evaluation_report.txt").write_text(build_report(metrics), encoding="utf-8")
    return metrics


def build_report(m: dict) -> str:
    tr, te = m["split"]["train"], m["split"]["test"]
    model = m["test_metrics"]["model"]
    base = m["test_metrics"]["baseline_training_goal_rate"]
    sb = m["test_metrics"]["statsbomb_xg_benchmark"]

    def compare(name: str, lower_is_better: bool) -> str:
        ours, ref = model[name], base[name]
        better = ours < ref if lower_is_better else ours > ref
        return "better than" if better else "NOT better than"

    auc = model["roc_auc"]
    auc_line = (
        f"  ROC-AUC     {auc:.4f}  (base rate 0.5000, StatsBomb xG {sb['roc_auc']:.4f})\n"
        if auc is not None else "  ROC-AUC     not computed: the test split has only one class\n"
    )
    return f"""FootStat - model evaluation report
Generated {m['trained_at']} by scripts/train_model.py. All numbers are computed
on held-out matches the model never saw during training.

Data split (by match, seed {m['split']['random_seed']})
  Train: {tr['matches']} matches, {tr['shots']} shots, {tr['goals']} goals ({tr['goal_rate']:.1%})
  Test:  {te['matches']} matches, {te['shots']} shots, {te['goals']} goals ({te['goal_rate']:.1%})

Results on the test matches
  Log loss    {model['log_loss']:.4f}  (base rate {base['log_loss']:.4f}, StatsBomb xG {sb['log_loss']:.4f})
  Brier score {model['brier_score']:.4f}  (base rate {base['brier_score']:.4f}, StatsBomb xG {sb['brier_score']:.4f})
{auc_line}  Mean predicted xG {model['mean_predicted']:.4f} vs observed goal rate {m['observed_test_goal_rate']:.4f}

What these mean
  Log loss: how surprised the model is by what actually happened. Lower is
    better. Confident wrong predictions are punished heavily.
  Brier score: mean squared gap between the predicted probability and the
    outcome (0 or 1). Lower is better.
  ROC-AUC: chance that a randomly chosen goal gets a higher xG than a randomly
    chosen non-goal. 0.5 is random ordering, 1.0 is perfect ranking. It says
    nothing about whether the probabilities themselves are well scaled.
  Base rate: predicting the training goal rate for every shot. A useful
    model has to beat this.
  StatsBomb xG: the provider's own model, shown only as a benchmark. It uses
    far more information (defender and goalkeeper positions, shot type, etc.)
    and was never an input to this model.

Verdict
  On log loss the model is {compare('log_loss', True)} the base rate; on Brier
  score it is {compare('brier_score', True)} the base rate.

Caveats
  - The test set is small ({te['shots']} shots, {te['goals']} goals), so these
    numbers would move noticeably with a different split or more matches.
  - Features are location and body part only. Shot type is not a feature, so
    penalties are treated like any open-play shot from the penalty spot and
    will be under-predicted.
  - Data is a single tournament (FIFA World Cup 2022).
"""


def main() -> None:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    try:
        metrics = train_and_evaluate()
    except InsufficientDataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print((ARTIFACTS_DIR / "evaluation_report.txt").read_text(encoding="utf-8"))
    print(f"Saved {ARTIFACTS_DIR / 'model.joblib'} and metrics.json")


if __name__ == "__main__":
    main()
