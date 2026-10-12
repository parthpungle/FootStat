"""Checks that the saved model artifact loads and returns valid probabilities.

Requires a trained model: run `python -m scripts.train_model` first.
"""

from pathlib import Path

import joblib
import numpy as np
import pytest

from app.services.xg_features import to_model_input

MODEL_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "model.joblib"

VALID_SHOTS = [
    {"x": 108.0, "y": 40.0, "body_part": "Right Foot"},
    {"x": 114.0, "y": 38.5, "body_part": "Head"},
    {"x": 95.0, "y": 25.0, "body_part": "Left Foot"},
    {"x": 120.0, "y": 40.0, "body_part": "Other"},  # on the goal line
    {"x": 60.0, "y": 0.0, "body_part": "Right Foot"},  # halfway line, touchline
]


@pytest.fixture(scope="module")
def model():
    assert MODEL_PATH.exists(), f"{MODEL_PATH} not found; run `python -m scripts.train_model`"
    return joblib.load(MODEL_PATH)


def test_artifact_loads_as_probabilistic_classifier(model):
    assert hasattr(model, "predict_proba")
    assert list(model.classes_) == [0, 1]


def test_predictions_are_finite_probabilities(model):
    probs = model.predict_proba(to_model_input(VALID_SHOTS))[:, 1]
    assert probs.shape == (len(VALID_SHOTS),)
    assert np.all(np.isfinite(probs))
    assert np.all((probs >= 0) & (probs <= 1))


def test_single_shot_prediction(model):
    prob = model.predict_proba(to_model_input([VALID_SHOTS[0]]))[0, 1]
    assert 0.0 <= prob <= 1.0


def test_unseen_body_part_is_handled(model):
    probs = model.predict_proba(to_model_input([{"x": 110.0, "y": 40.0, "body_part": "Knee"}]))[:, 1]
    assert np.all(np.isfinite(probs)) and 0.0 <= probs[0] <= 1.0


def test_closer_central_shot_scores_higher_than_long_range(model):
    near, far = model.predict_proba(to_model_input([
        {"x": 114.0, "y": 40.0, "body_part": "Right Foot"},
        {"x": 85.0, "y": 40.0, "body_part": "Right Foot"},
    ]))[:, 1]
    assert near > far


def test_missing_input_column_is_rejected():
    with pytest.raises(ValueError):
        to_model_input([{"x": 110.0, "y": 40.0}])
