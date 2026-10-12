"""API tests. Require the processed dataset and trained model:

    python -m scripts.build_shots_dataset
    python -m scripts.train_model
"""

import json
import math
import re
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.api import BodyPart
from app.services.data_store import DEFAULT_METRICS_PATH, DEFAULT_SHOTS_PATH

REPORT_PATH = DEFAULT_METRICS_PATH.with_name("evaluation_report.txt")


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:  # context manager runs the startup lifespan
        yield c


def assert_json_finite(obj):
    """Fail on any NaN/Infinity anywhere in a decoded JSON payload."""
    if isinstance(obj, float):
        assert math.isfinite(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            assert_json_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            assert_json_finite(v)


# --- Health -----------------------------------------------------------------

def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] and body["dataset_available"] and body["metrics_available"]
    assert body["model_version"].startswith("logreg-")


def test_health_unavailable_when_files_missing(tmp_path: Path):
    app = create_app(
        model_path=tmp_path / "missing.joblib",
        metrics_path=tmp_path / "missing.json",
        shots_path=tmp_path / "missing.csv",
        matches_path=tmp_path / "missing_matches.csv",
    )
    with TestClient(app) as c:
        r = c.get("/api/health")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "unavailable"
        assert not body["model_loaded"] and not body["dataset_available"]
        assert {"model", "dataset", "metrics"} <= set(body["errors"])

        assert c.get("/api/overview").status_code == 503
        assert c.get("/api/shots").status_code == 503
        assert c.get("/api/metrics").status_code == 503
        assert c.post("/api/predict", json={"x": 110, "y": 40, "body_part": "Head"}).status_code == 503


# --- Overview ---------------------------------------------------------------

def test_overview(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()
    assert_json_finite(body)

    shots = pd.read_csv(DEFAULT_SHOTS_PATH)
    assert body["total_shots"] == len(shots)
    assert body["total_goals"] == int(shots["goal"].sum())
    assert body["total_non_goals"] == int((shots["goal"] == 0).sum())
    assert 0 < body["total_predicted_xg"] < body["total_shots"]

    top = body["top_players"]
    assert len(top) == 5
    assert [p["predicted_xg"] for p in top] == sorted((p["predicted_xg"] for p in top), reverse=True)

    assert len(body["by_match"]) == shots["match_id"].nunique()
    assert sum(m["goals"] for m in body["by_match"]) == body["total_goals"]
    assert all(m["match_date"] for m in body["by_match"])
    assert sum(d["matches"] for d in body["by_date"]) == len(body["by_match"])


def test_overview_xg_matches_sum_of_shot_xg(client):
    overview = client.get("/api/overview").json()
    shots = client.get("/api/shots", params={"limit": 2000}).json()
    assert shots["total"] == overview["total_shots"]
    total = sum(s["predicted_xg"] for s in shots["items"])
    assert total == pytest.approx(overview["total_predicted_xg"], abs=0.1)  # per-shot values are rounded


# --- Shots ------------------------------------------------------------------

def test_shots_default(client):
    r = client.get("/api/shots")
    assert r.status_code == 200
    body = r.json()
    assert_json_finite(body)
    assert body["limit"] == 500 and body["offset"] == 0
    assert len(body["items"]) == min(500, body["total"])
    shot = body["items"][0]
    for key in ("event_id", "match_id", "player_name", "team_name", "x", "y", "goal", "predicted_xg", "statsbomb_xg"):
        assert key in shot
    assert 0 <= shot["x"] <= 120 and 0 <= shot["y"] <= 80
    assert 0 <= shot["predicted_xg"] <= 1


def test_shots_filters_and_pagination(client):
    goals = client.get("/api/shots", params={"outcome": "goal", "limit": 2000}).json()
    assert goals["total"] > 0 and all(s["goal"] for s in goals["items"])

    team = client.get("/api/shots", params={"team": "argentina", "limit": 2000}).json()
    assert team["total"] > 0 and all(s["team_name"] == "Argentina" for s in team["items"])

    player = client.get("/api/shots", params={"player": "messi"}).json()
    assert player["total"] > 0 and all("Messi" in s["player_name"] for s in player["items"])

    page1 = client.get("/api/shots", params={"limit": 10, "offset": 0}).json()["items"]
    page2 = client.get("/api/shots", params={"limit": 10, "offset": 10}).json()["items"]
    assert {s["event_id"] for s in page1}.isdisjoint(s["event_id"] for s in page2)


def test_shots_player_filter_ignores_accents(client):
    accented = client.get("/api/shots", params={"player": "Mbappé", "limit": 2000}).json()
    plain = client.get("/api/shots", params={"player": "mbappe", "limit": 2000}).json()
    assert accented["total"] > 0 and plain["total"] == accented["total"]
    assert client.get("/api/shots", params={"player": "alvarez"}).json()["total"] > 0


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 5000}, {"offset": -1}, {"outcome": "maybe"}])
def test_shots_invalid_params(client, params):
    assert client.get("/api/shots", params=params).status_code == 422


# --- Predict ----------------------------------------------------------------

@pytest.mark.parametrize("body_part", [b.value for b in BodyPart])
def test_predict_valid(client, body_part):
    r = client.post("/api/predict", json={"x": 108, "y": 40, "body_part": body_part})
    assert r.status_code == 200
    body = r.json()
    assert math.isfinite(body["predicted_xg"]) and 0 <= body["predicted_xg"] <= 1
    assert body["model_version"].startswith("logreg-")
    assert body["distance"] == pytest.approx(12.0)


def test_predict_matches_historical_shot_xg(client):
    shot = client.get("/api/shots", params={"limit": 1}).json()["items"][0]
    r = client.post("/api/predict", json={"x": shot["x"], "y": shot["y"], "body_part": shot["body_part"]})
    assert r.json()["predicted_xg"] == pytest.approx(shot["predicted_xg"], abs=1e-4)


def test_predict_closer_shot_has_higher_xg(client):
    near = client.post("/api/predict", json={"x": 114, "y": 40, "body_part": "Right Foot"}).json()
    far = client.post("/api/predict", json={"x": 85, "y": 40, "body_part": "Right Foot"}).json()
    assert near["predicted_xg"] > far["predicted_xg"]


@pytest.mark.parametrize("payload", [
    {"x": 121, "y": 40, "body_part": "Head"},
    {"x": -1, "y": 40, "body_part": "Head"},
    {"x": 100, "y": 80.5, "body_part": "Head"},
    {"x": 100, "y": -0.1, "body_part": "Head"},
    {"x": 100, "y": 40, "body_part": "Knee"},
    {"x": 100, "y": 40},
    {"x": "far", "y": 40, "body_part": "Head"},
    {"x": 100, "y": 40, "body_part": "Head", "statsbomb_xg": 0.9},
])
def test_predict_invalid_input(client, payload):
    assert client.post("/api/predict", json=payload).status_code == 422


def test_predict_rejects_nan(client):
    r = client.post("/api/predict", content='{"x": NaN, "y": 40, "body_part": "Head"}',
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_body_part_enum_matches_trained_encoder(client):
    model = client.app.state.store.model
    encoder = model.named_steps["preprocess"].named_transformers_["categorical"].named_steps["onehot"]
    assert set(encoder.categories_[0]) == {b.value for b in BodyPart}


# --- Metrics ----------------------------------------------------------------

def test_metrics_match_saved_evaluation(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    saved = json.loads(DEFAULT_METRICS_PATH.read_text(encoding="utf-8"))

    assert body["test_metrics"] == saved["test_metrics"]["model"]
    assert body["statsbomb_xg_benchmark"] == saved["test_metrics"]["statsbomb_xg_benchmark"]
    assert body["test_examples"] == saved["split"]["test"]["shots"]
    assert body["trained_at"] == saved["trained_at"]

    report = REPORT_PATH.read_text(encoding="utf-8")

    def report_value(label: str) -> float:
        return float(re.search(rf"^\s*{label}\s+([0-9.]+)", report, re.MULTILINE).group(1))

    assert report_value("Log loss") == pytest.approx(body["test_metrics"]["log_loss"])
    assert report_value("Brier score") == pytest.approx(body["test_metrics"]["brier_score"])
    assert report_value("ROC-AUC") == pytest.approx(body["test_metrics"]["roc_auc"])
    test_shots = int(re.search(r"Test:\s+\d+ matches, (\d+) shots", report).group(1))
    assert test_shots == body["test_examples"]


def test_cors_allows_vite_origin(client):
    r = client.options("/api/predict", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
