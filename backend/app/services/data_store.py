"""Loads the model, processed data and metrics once, at application startup.

Missing or unreadable files do not crash the app: each failure is recorded in
`errors`, /api/health reports it, and endpoints that depend on it return 503.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import pandas as pd

from app.services.xg_features import to_model_input

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = BACKEND_DIR / "artifacts" / "model.joblib"
DEFAULT_METRICS_PATH = BACKEND_DIR / "artifacts" / "metrics.json"
DEFAULT_SHOTS_PATH = BACKEND_DIR / "data" / "processed" / "shots.csv"
DEFAULT_MATCHES_PATH = BACKEND_DIR / "data" / "processed" / "matches.csv"

REQUIRED_SHOT_COLUMNS = {
    "match_id", "event_id", "player_id", "player_name", "team_id", "team_name",
    "x", "y", "body_part", "shot_type", "shot_outcome", "goal", "statsbomb_xg",
}


@dataclass
class DataStore:
    model: object | None = None
    model_version: str | None = None
    shots: pd.DataFrame | None = None  # includes a predicted_xg column
    matches: pd.DataFrame | None = None  # optional metadata
    metrics: dict | None = None
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def model_loaded(self) -> bool:
        return self.model is not None

    @property
    def dataset_available(self) -> bool:
        return self.shots is not None

    @property
    def metrics_available(self) -> bool:
        return self.metrics is not None


def _model_version(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"logreg-{digest}"


def load_store(
    model_path: Path = DEFAULT_MODEL_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    shots_path: Path = DEFAULT_SHOTS_PATH,
    matches_path: Path = DEFAULT_MATCHES_PATH,
) -> DataStore:
    store = DataStore()

    try:
        store.model = joblib.load(model_path)
        store.model_version = _model_version(model_path)
    except Exception as exc:  # missing file, unpickling error, version mismatch...
        store.errors["model"] = f"Could not load {model_path.name}: {exc}"

    try:
        with open(metrics_path, encoding="utf-8") as f:
            store.metrics = json.load(f)
    except Exception as exc:
        store.errors["metrics"] = f"Could not load {metrics_path.name}: {exc}"

    try:
        shots = pd.read_csv(shots_path)
        missing = REQUIRED_SHOT_COLUMNS - set(shots.columns)
        if missing:
            raise ValueError(f"missing columns {sorted(missing)}")
        if store.model is not None:
            # Score historical shots once; requests only read the result.
            shots["predicted_xg"] = store.model.predict_proba(to_model_input(shots))[:, 1]
        store.shots = shots
    except Exception as exc:
        store.errors["dataset"] = f"Could not load {shots_path.name}: {exc}"

    try:
        store.matches = pd.read_csv(matches_path)
    except Exception as exc:
        # Optional: overview falls back to match IDs without dates/teams.
        store.errors["matches"] = f"Could not load {matches_path.name}: {exc}"

    return store
