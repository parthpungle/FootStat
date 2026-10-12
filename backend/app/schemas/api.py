"""Request and response models for the FootStat API."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.services.shot_geometry import PITCH_LENGTH, PITCH_WIDTH


class BodyPart(str, Enum):
    """Body parts the model was trained on (StatsBomb names)."""

    RIGHT_FOOT = "Right Foot"
    LEFT_FOOT = "Left Foot"
    HEAD = "Head"
    OTHER = "Other"


class OutcomeFilter(str, Enum):
    GOAL = "goal"
    NO_GOAL = "no_goal"


# --- Health -----------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = Field(description='"ok" only when the model and dataset are both available')
    model_loaded: bool
    dataset_available: bool
    metrics_available: bool
    model_version: str | None
    errors: dict[str, str] = Field(description="Load problems by component; empty when all files loaded")


# --- Overview ---------------------------------------------------------------

class PlayerXg(BaseModel):
    player_id: int
    player_name: str
    team_name: str
    shots: int
    goals: int
    predicted_xg: float
    statsbomb_xg: float | None


class MatchXg(BaseModel):
    match_id: int
    match_date: str | None
    home_team: str | None
    away_team: str | None
    shots: int
    goals: int
    predicted_xg: float
    statsbomb_xg: float | None


class DateXg(BaseModel):
    match_date: str
    matches: int
    shots: int
    goals: int
    predicted_xg: float


class OverviewResponse(BaseModel):
    total_shots: int
    total_goals: int
    total_non_goals: int
    total_predicted_xg: float | None = Field(description="null if the model is not loaded")
    total_statsbomb_xg: float | None = Field(description="Benchmark; null if unavailable")
    top_players: list[PlayerXg] = Field(description="Top 5 by predicted xG; empty if the model is not loaded")
    by_match: list[MatchXg] = Field(description="Sorted by date, then match_id; empty if the model is not loaded")
    by_date: list[DateXg] = Field(description="Empty if match dates are unavailable or the model is not loaded")


# --- Shots ------------------------------------------------------------------

class ShotRecord(BaseModel):
    event_id: str
    match_id: int
    player_id: int | None
    player_name: str | None
    team_id: int | None
    team_name: str | None
    x: float
    y: float
    body_part: str | None
    shot_type: str | None
    shot_outcome: str
    goal: bool
    predicted_xg: float
    statsbomb_xg: float | None


class ShotsResponse(BaseModel):
    total: int = Field(description="Records matching the filters, before limit/offset")
    limit: int
    offset: int
    items: list[ShotRecord]


# --- Predict ----------------------------------------------------------------

class PredictRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    x: float = Field(ge=0, le=PITCH_LENGTH, description="StatsBomb x, 0-120; attacking goal at x=120")
    y: float = Field(ge=0, le=PITCH_WIDTH, description="StatsBomb y, 0-80; goal centre at y=40")
    body_part: BodyPart


class PredictResponse(BaseModel):
    predicted_xg: float = Field(ge=0, le=1)
    model_version: str
    distance: float = Field(description="Distance to the centre of the goal, pitch units")
    angle: float = Field(description="Angle subtended by the goalposts, radians")
    angle_degrees: float


# --- Metrics ----------------------------------------------------------------

class ScoreSet(BaseModel):
    log_loss: float
    brier_score: float
    roc_auc: float | None
    mean_predicted: float


class SplitSummary(BaseModel):
    matches: int
    shots: int
    goals: int
    non_goals: int
    goal_rate: float


class MetricsResponse(BaseModel):
    model: str
    model_version: str | None
    trained_at: str
    test_examples: int
    train: SplitSummary
    test: SplitSummary
    test_metrics: ScoreSet
    baseline_training_goal_rate: ScoreSet
    statsbomb_xg_benchmark: ScoreSet
