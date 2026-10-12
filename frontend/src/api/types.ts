// Mirrors the Pydantic schemas in backend/app/schemas/api.py.

/** Body parts the model was trained on (backend BodyPart enum). */
export const BODY_PARTS = ['Right Foot', 'Left Foot', 'Head', 'Other'] as const
export type BodyPart = (typeof BODY_PARTS)[number]

export type OutcomeFilter = 'goal' | 'no_goal'

export interface HealthResponse {
  status: string
  model_loaded: boolean
  dataset_available: boolean
  metrics_available: boolean
  model_version: string | null
  errors: Record<string, string>
}

export interface PlayerXg {
  player_id: number
  player_name: string
  team_name: string
  shots: number
  goals: number
  predicted_xg: number
  statsbomb_xg: number | null
}

export interface MatchXg {
  match_id: number
  match_date: string | null
  home_team: string | null
  away_team: string | null
  shots: number
  goals: number
  predicted_xg: number
  statsbomb_xg: number | null
}

export interface DateXg {
  match_date: string
  matches: number
  shots: number
  goals: number
  predicted_xg: number
}

export interface OverviewResponse {
  total_shots: number
  total_goals: number
  total_non_goals: number
  total_predicted_xg: number | null
  total_statsbomb_xg: number | null
  top_players: PlayerXg[]
  by_match: MatchXg[]
  by_date: DateXg[]
}

export interface ShotRecord {
  event_id: string
  match_id: number
  player_id: number | null
  player_name: string | null
  team_id: number | null
  team_name: string | null
  x: number
  y: number
  body_part: string | null
  shot_type: string | null
  shot_outcome: string
  goal: boolean
  predicted_xg: number
  statsbomb_xg: number | null
}

export interface ShotsResponse {
  total: number
  limit: number
  offset: number
  items: ShotRecord[]
}

export interface ShotsQuery {
  player?: string
  team?: string
  outcome?: OutcomeFilter
  match_id?: number
  limit?: number
  offset?: number
}

export interface PredictRequest {
  x: number
  y: number
  body_part: BodyPart
}

export interface PredictResponse {
  predicted_xg: number
  model_version: string
  distance: number
  angle: number
  angle_degrees: number
}

export interface ScoreSet {
  log_loss: number
  brier_score: number
  roc_auc: number | null
  mean_predicted: number
}

export interface SplitSummary {
  matches: number
  shots: number
  goals: number
  non_goals: number
  goal_rate: number
}

export interface MetricsResponse {
  model: string
  model_version: string | null
  trained_at: string
  test_examples: number
  train: SplitSummary
  test: SplitSummary
  test_metrics: ScoreSet
  baseline_training_goal_rate: ScoreSet
  statsbomb_xg_benchmark: ScoreSet
}
