"""FootStat API endpoints, all under /api."""

import math
import unicodedata

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.schemas.api import (
    DateXg,
    HealthResponse,
    MatchXg,
    MetricsResponse,
    OutcomeFilter,
    OverviewResponse,
    PlayerXg,
    PredictRequest,
    PredictResponse,
    ShotRecord,
    ShotsResponse,
)
from app.services.data_store import DataStore
from app.services.shot_geometry import shot_angle, shot_distance
from app.services.xg_features import to_model_input

router = APIRouter(prefix="/api")

MAX_SHOTS_LIMIT = 2000
DEFAULT_SHOTS_LIMIT = 500
TOP_PLAYERS = 5


def fold(text: str) -> str:
    """Lower-case and strip accents, so "mbappe" matches "Mbappé"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def name_contains(column: pd.Series, query: str) -> pd.Series:
    return column.fillna("").map(fold).str.contains(fold(query), regex=False)


def get_store(request: Request) -> DataStore:
    return request.app.state.store


def require_dataset(store: DataStore) -> pd.DataFrame:
    if not store.dataset_available:
        raise HTTPException(503, f"Processed dataset unavailable: {store.errors.get('dataset', 'not loaded')}")
    return store.shots


def require_model(store: DataStore) -> None:
    if not store.model_loaded:
        raise HTTPException(503, f"Model unavailable: {store.errors.get('model', 'not loaded')}")


def clean(value):
    """Convert pandas/numpy scalars to JSON-safe Python values (NaN/inf -> None)."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return None if not math.isfinite(value) else float(value)
    return value


def xg(value) -> float | None:
    value = clean(value)
    return round(value, 4) if value is not None else None


# --- Health -----------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
def health(store: DataStore = Depends(get_store)):
    # matches.csv is optional metadata, so it never makes the service unhealthy.
    healthy = store.model_loaded and store.dataset_available and store.metrics_available
    body = HealthResponse(
        status="ok" if healthy else "unavailable",
        model_loaded=store.model_loaded,
        dataset_available=store.dataset_available,
        metrics_available=store.metrics_available,
        model_version=store.model_version,
        errors=store.errors,
    )
    return JSONResponse(body.model_dump(), status_code=200 if healthy else 503)


# --- Overview ---------------------------------------------------------------

@router.get("/overview", response_model=OverviewResponse)
def overview(store: DataStore = Depends(get_store)):
    shots = require_dataset(store)
    goals = int(shots["goal"].sum())
    has_xg = "predicted_xg" in shots.columns

    result = OverviewResponse(
        total_shots=len(shots),
        total_goals=goals,
        total_non_goals=len(shots) - goals,
        total_predicted_xg=xg(shots["predicted_xg"].sum()) if has_xg else None,
        total_statsbomb_xg=xg(shots["statsbomb_xg"].sum(min_count=1)),
        top_players=[],
        by_match=[],
        by_date=[],
    )
    if not has_xg:
        return result

    players = (
        shots.dropna(subset=["player_id"])
        .groupby("player_id")
        .agg(
            player_name=("player_name", "first"),
            team_name=("team_name", "first"),
            shots=("event_id", "size"),
            goals=("goal", "sum"),
            predicted_xg=("predicted_xg", "sum"),
            statsbomb_xg=("statsbomb_xg", lambda s: s.sum(min_count=1)),
        )
        .sort_values(["predicted_xg", "player_name"], ascending=[False, True])
        .head(TOP_PLAYERS)
    )
    result.top_players = [
        PlayerXg(
            player_id=int(pid), player_name=r.player_name, team_name=r.team_name,
            shots=int(r.shots), goals=int(r.goals),
            predicted_xg=xg(r.predicted_xg), statsbomb_xg=xg(r.statsbomb_xg),
        )
        for pid, r in players.iterrows()
    ]

    per_match = shots.groupby("match_id").agg(
        shots=("event_id", "size"),
        goals=("goal", "sum"),
        predicted_xg=("predicted_xg", "sum"),
        statsbomb_xg=("statsbomb_xg", lambda s: s.sum(min_count=1)),
    ).reset_index()
    if store.matches is not None and {"match_id", "match_date", "home_team", "away_team"} <= set(store.matches.columns):
        meta = store.matches[["match_id", "match_date", "home_team", "away_team"]]
        per_match = per_match.merge(meta, on="match_id", how="left")
    else:
        per_match = per_match.assign(match_date=None, home_team=None, away_team=None)
    per_match = per_match.sort_values(["match_date", "match_id"], na_position="last")

    result.by_match = [
        MatchXg(
            match_id=int(r.match_id), match_date=clean(r.match_date),
            home_team=clean(r.home_team), away_team=clean(r.away_team),
            shots=int(r.shots), goals=int(r.goals),
            predicted_xg=xg(r.predicted_xg), statsbomb_xg=xg(r.statsbomb_xg),
        )
        for r in per_match.itertuples()
    ]

    dated = per_match.dropna(subset=["match_date"])
    if not dated.empty:
        per_date = dated.groupby("match_date").agg(
            matches=("match_id", "size"),
            shots=("shots", "sum"),
            goals=("goals", "sum"),
            predicted_xg=("predicted_xg", "sum"),
        ).reset_index()
        result.by_date = [
            DateXg(
                match_date=str(r.match_date), matches=int(r.matches), shots=int(r.shots),
                goals=int(r.goals), predicted_xg=xg(r.predicted_xg),
            )
            for r in per_date.itertuples()
        ]
    return result


# --- Shots ------------------------------------------------------------------

@router.get("/shots", response_model=ShotsResponse)
def list_shots(
    player: str | None = Query(None, description="Case- and accent-insensitive substring of the player name"),
    team: str | None = Query(None, description="Case- and accent-insensitive substring of the team name"),
    outcome: OutcomeFilter | None = Query(None, description='"goal" or "no_goal"'),
    match_id: int | None = Query(None),
    limit: int = Query(DEFAULT_SHOTS_LIMIT, ge=1, le=MAX_SHOTS_LIMIT),
    offset: int = Query(0, ge=0),
    store: DataStore = Depends(get_store),
):
    shots = require_dataset(store)
    require_model(store)

    mask = pd.Series(True, index=shots.index)
    if player:
        mask &= name_contains(shots["player_name"], player)
    if team:
        mask &= name_contains(shots["team_name"], team)
    if outcome is not None:
        mask &= shots["goal"] == (1 if outcome is OutcomeFilter.GOAL else 0)
    if match_id is not None:
        mask &= shots["match_id"] == match_id

    filtered = shots[mask]
    page = filtered.iloc[offset: offset + limit]
    items = [
        ShotRecord(
            event_id=r.event_id, match_id=int(r.match_id),
            player_id=clean(r.player_id), player_name=clean(r.player_name),
            team_id=clean(r.team_id), team_name=clean(r.team_name),
            x=float(r.x), y=float(r.y),
            body_part=clean(r.body_part), shot_type=clean(r.shot_type),
            shot_outcome=r.shot_outcome, goal=bool(r.goal),
            predicted_xg=xg(r.predicted_xg), statsbomb_xg=xg(r.statsbomb_xg),
        )
        for r in page.itertuples()
    ]
    return ShotsResponse(total=len(filtered), limit=limit, offset=offset, items=items)


# --- Predict ----------------------------------------------------------------

@router.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest, store: DataStore = Depends(get_store)):
    require_model(store)
    features = to_model_input([{"x": request.x, "y": request.y, "body_part": request.body_part.value}])
    probability = float(store.model.predict_proba(features)[0, 1])
    if not (math.isfinite(probability) and 0.0 <= probability <= 1.0):
        raise HTTPException(500, "Model returned an invalid probability")

    # Same helpers the pipeline uses internally, returned for display.
    angle = float(shot_angle(request.x, request.y))
    return PredictResponse(
        predicted_xg=round(probability, 6),
        model_version=store.model_version,
        distance=round(float(shot_distance(request.x, request.y)), 4),
        angle=round(angle, 6),
        angle_degrees=round(math.degrees(angle), 2),
    )


# --- Metrics ----------------------------------------------------------------

@router.get("/metrics", response_model=MetricsResponse)
def metrics(store: DataStore = Depends(get_store)):
    if not store.metrics_available:
        raise HTTPException(503, f"Metrics unavailable: {store.errors.get('metrics', 'not loaded')}")
    m = store.metrics
    try:
        return MetricsResponse(
            model=m["model"],
            model_version=store.model_version,
            trained_at=m["trained_at"],
            test_examples=m["split"]["test"]["shots"],
            train=m["split"]["train"],
            test=m["split"]["test"],
            test_metrics=m["test_metrics"]["model"],
            baseline_training_goal_rate=m["test_metrics"]["baseline_training_goal_rate"],
            statsbomb_xg_benchmark=m["test_metrics"]["statsbomb_xg_benchmark"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(500, f"metrics.json has an unexpected format: {exc}") from exc
