"""Feature preparation shared by model training and prediction.

The saved model pipeline takes only the raw inputs in INPUT_COLUMNS. Distance
and angle are derived inside the pipeline by add_geometry_features, so training
and inference cannot drift apart.

Never add statsbomb_xg, shot_outcome or any other post-shot field here.
"""

import pandas as pd

from app.services.shot_geometry import shot_angle, shot_distance

INPUT_COLUMNS = ["x", "y", "body_part"]
NUMERIC_FEATURES = ["x", "y", "distance", "angle"]
CATEGORICAL_FEATURES = ["body_part"]


def add_geometry_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the raw inputs with distance and angle added."""
    out = frame[INPUT_COLUMNS].copy()
    out["distance"] = shot_distance(out["x"], out["y"])
    out["angle"] = shot_angle(out["x"], out["y"])
    return out


def to_model_input(records) -> pd.DataFrame:
    """Build the pipeline's input frame from a DataFrame or a list of dicts."""
    frame = pd.DataFrame(records)
    missing = [c for c in INPUT_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Missing model input columns: {missing}")
    frame = frame[INPUT_COLUMNS].copy()
    frame["x"] = frame["x"].astype(float)
    frame["y"] = frame["y"].astype(float)
    frame["body_part"] = frame["body_part"].astype(object)
    return frame
