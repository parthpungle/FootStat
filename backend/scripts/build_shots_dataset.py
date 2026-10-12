"""Download StatsBomb Open Data for one competition season and build shots.csv.

Run from the backend/ directory:

    python -m scripts.build_shots_dataset
    python -m scripts.build_shots_dataset --competition-id 43 --season-id 106 --max-matches 10

Raw JSON is cached (gzipped) under data/raw/statsbomb/, so re-runs are offline
unless --refresh is passed. Outputs, all in data/processed/:

    shots.csv          one row per valid shot
    matches.csv        the matches processed, with shot/goal counts
    shots_report.json  counts, exclusions, missing values, coordinate ranges

Data rules:
- Only events with type "Shot" are shots. Own goals are separate event types
  and are counted for score reconciliation only, never as shots.
- Penalty shootout attempts (period 5) are excluded: they are not part of the
  match and do not change the score.
- goal = 1 when the shot outcome is "Goal", otherwise 0 for every other known
  outcome (Saved, Blocked, Off T, Post, Wayward, Saved Off Target, Saved to Post).
- Shots without a usable location or outcome are excluded and counted.
- statsbomb_xg and shot_outcome are kept for benchmarking/display only. They
  (and anything else known only after the shot) must not be model inputs.
  end_location is post-shot information and is not extracted.
"""

import argparse
import gzip
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.shot_geometry import PITCH_LENGTH, PITCH_WIDTH, shot_angle, shot_distance  # noqa: E402

SOURCE_BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
RAW_DIR = BACKEND_DIR / "data" / "raw" / "statsbomb"
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"

# FIFA World Cup 2022: one complete tournament, 64 matches.
DEFAULT_COMPETITION_ID = 43
DEFAULT_SEASON_ID = 106

SHOOTOUT_PERIOD = 5
GOAL_OUTCOME = "Goal"
NON_GOAL_OUTCOMES = {"Saved", "Blocked", "Off T", "Post", "Wayward", "Saved Off Target", "Saved to Post"}
OWN_GOAL_FOR = "Own Goal For"

SHOT_COLUMNS = [
    "match_id", "event_id", "period", "minute", "second",
    "team_id", "team_name", "player_id", "player_name",
    "x", "y", "distance", "angle",
    "shot_type", "body_part", "technique", "play_pattern",
    "first_time", "under_pressure",
    "shot_outcome", "goal", "statsbomb_xg",
]


# --- Download / cache -------------------------------------------------------

def fetch_json(url: str, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries:
                raise RuntimeError(f"Failed to download {url}: {exc}") from exc
            time.sleep(2 * attempt)


def load_cached(path: Path, url: str, refresh: bool):
    """Return JSON from a gzipped cache file, downloading it first if needed."""
    if path.exists() and not refresh:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    data = fetch_json(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def load_matches(competition_id: int, season_id: int, refresh: bool) -> list[dict]:
    path = RAW_DIR / "matches" / f"{competition_id}_{season_id}.json.gz"
    url = f"{SOURCE_BASE_URL}/matches/{competition_id}/{season_id}.json"
    return load_cached(path, url, refresh)


def load_events(match_id: int, refresh: bool) -> list[dict]:
    path = RAW_DIR / "events" / f"{match_id}.json.gz"
    url = f"{SOURCE_BASE_URL}/events/{match_id}.json"
    return load_cached(path, url, refresh)


# --- Parsing ----------------------------------------------------------------

def nested_name(obj: dict, *keys: str):
    """Follow keys through nested dicts and return the final 'name', or None."""
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj.get("name") if isinstance(obj, dict) else None


def nested_id(obj: dict, key: str):
    value = obj.get(key)
    return value.get("id") if isinstance(value, dict) else None


def parse_location(location):
    """Return (x, y) if location is two finite numbers on the pitch, else None."""
    if not isinstance(location, list) or len(location) < 2:
        return None
    x, y = location[0], location[1]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (x, y)):
        return None
    if not (0 <= x <= PITCH_LENGTH and 0 <= y <= PITCH_WIDTH):
        return None
    return float(x), float(y)


def extract_shots(match_id: int, events: list[dict], exclusions: Counter) -> list[dict]:
    rows = []
    for event in events:
        if nested_name(event, "type") != "Shot":
            continue
        if event.get("period") == SHOOTOUT_PERIOD:
            exclusions["penalty_shootout_attempt"] += 1
            continue

        shot = event.get("shot")
        if not isinstance(shot, dict):
            exclusions["missing_shot_object"] += 1
            continue

        coords = parse_location(event.get("location"))
        if coords is None:
            exclusions["missing_or_invalid_location"] += 1
            continue

        outcome = nested_name(shot, "outcome")
        if outcome == GOAL_OUTCOME:
            goal = 1
        elif outcome in NON_GOAL_OUTCOMES:
            goal = 0
        elif outcome is None:
            exclusions["missing_outcome"] += 1
            continue
        else:
            exclusions[f"unrecognised_outcome:{outcome}"] += 1
            continue

        xg = shot.get("statsbomb_xg")
        rows.append({
            "match_id": match_id,
            "event_id": event.get("id"),
            "period": event.get("period"),
            "minute": event.get("minute"),
            "second": event.get("second"),
            "team_id": nested_id(event, "team"),
            "team_name": nested_name(event, "team"),
            "player_id": nested_id(event, "player"),
            "player_name": nested_name(event, "player"),
            "x": coords[0],
            "y": coords[1],
            "shot_type": nested_name(shot, "type"),
            "body_part": nested_name(shot, "body_part"),
            "technique": nested_name(shot, "technique"),
            "play_pattern": nested_name(event, "play_pattern"),
            # StatsBomb only includes these boolean flags when they are true;
            # absence means false per the event specification.
            "first_time": bool(shot.get("first_time", False)),
            "under_pressure": bool(event.get("under_pressure", False)),
            "shot_outcome": outcome,
            "goal": goal,
            "statsbomb_xg": float(xg) if isinstance(xg, (int, float)) else None,
        })
    return rows


def max_event_coordinates(events: list[dict]) -> tuple[float, float]:
    """Largest x and y seen in any event location, to sanity-check pitch size."""
    xs, ys = [0.0], [0.0]
    for event in events:
        loc = event.get("location")
        if isinstance(loc, list) and len(loc) >= 2:
            xs.append(loc[0])
            ys.append(loc[1])
    return max(xs), max(ys)


# --- Main -------------------------------------------------------------------

def build(competition_id: int, season_id: int, max_matches: int | None, refresh: bool) -> dict:
    matches = sorted(load_matches(competition_id, season_id, refresh), key=lambda m: m["match_id"])
    if max_matches:
        matches = matches[:max_matches]
    print(f"Loading events for {len(matches)} matches (competition {competition_id}, season {season_id})...")

    with ThreadPoolExecutor(max_workers=8) as pool:
        all_events = list(pool.map(lambda m: load_events(m["match_id"], refresh), matches))

    exclusions: Counter = Counter()
    shot_rows, match_rows = [], []
    event_max_x, event_max_y = 0.0, 0.0
    for match, events in zip(matches, all_events):
        match_id = match["match_id"]
        rows = extract_shots(match_id, events, exclusions)
        shot_rows.extend(rows)

        mx, my = max_event_coordinates(events)
        event_max_x, event_max_y = max(event_max_x, mx), max(event_max_y, my)

        own_goals = sum(1 for e in events if nested_name(e, "type") == OWN_GOAL_FOR)
        shot_goals = sum(r["goal"] for r in rows)
        final_goals = (match.get("home_score") or 0) + (match.get("away_score") or 0)
        match_rows.append({
            "match_id": match_id,
            "match_date": match.get("match_date"),
            "competition": match.get("competition", {}).get("competition_name"),
            "season": match.get("season", {}).get("season_name"),
            "stage": nested_name(match, "competition_stage"),
            "home_team": match.get("home_team", {}).get("home_team_name"),
            "away_team": match.get("away_team", {}).get("away_team_name"),
            "home_score": match.get("home_score"),
            "away_score": match.get("away_score"),
            "events": len(events),
            "shots": len(rows),
            "shot_goals": shot_goals,
            "own_goals": own_goals,
            "score_reconciles": shot_goals + own_goals == final_goals,
        })

    shots = pd.DataFrame(shot_rows)
    duplicates = int(shots["event_id"].duplicated().sum())
    if duplicates:
        exclusions["duplicate_event_id"] += duplicates
        shots = shots.drop_duplicates("event_id")

    shots["distance"] = shot_distance(shots["x"], shots["y"]).round(4)
    shots["angle"] = shot_angle(shots["x"], shots["y"]).round(6)
    shots["player_id"] = shots["player_id"].astype("Int64")
    shots["team_id"] = shots["team_id"].astype("Int64")
    shots = shots[SHOT_COLUMNS]
    matches_df = pd.DataFrame(match_rows)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    shots.to_csv(PROCESSED_DIR / "shots.csv", index=False)
    matches_df.to_csv(PROCESSED_DIR / "matches.csv", index=False)

    report = {
        "source": f"StatsBomb Open Data ({SOURCE_BASE_URL})",
        "competition_id": competition_id,
        "season_id": season_id,
        "matches_processed": len(matches_df),
        "shots": len(shots),
        "goals": int(shots["goal"].sum()),
        "non_goals": int((shots["goal"] == 0).sum()),
        "outcome_counts": shots["shot_outcome"].value_counts().to_dict(),
        "excluded_shots": dict(exclusions),
        "own_goals_not_counted_as_shots": int(matches_df["own_goals"].sum()),
        "matches_where_score_does_not_reconcile": matches_df.loc[~matches_df["score_reconciles"], "match_id"].tolist(),
        "missing_values": {c: int(n) for c, n in shots.isna().sum().items()},
        "coordinate_ranges": {
            "shot_x": [float(shots["x"].min()), float(shots["x"].max())],
            "shot_y": [float(shots["y"].min()), float(shots["y"].max())],
            "any_event_max_x": event_max_x,
            "any_event_max_y": event_max_y,
            "shots_in_own_half": int((shots["x"] < PITCH_LENGTH / 2).sum()),
        },
        "processed_match_ids": matches_df["match_id"].tolist(),
    }
    with open(PROCESSED_DIR / "shots_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--competition-id", type=int, default=DEFAULT_COMPETITION_ID)
    parser.add_argument("--season-id", type=int, default=DEFAULT_SEASON_ID)
    parser.add_argument("--max-matches", type=int, default=None, help="Limit to the first N matches by ID")
    parser.add_argument("--refresh", action="store_true", help="Re-download instead of using the raw cache")
    args = parser.parse_args()

    report = build(args.competition_id, args.season_id, args.max_matches, args.refresh)
    summary = {k: v for k, v in report.items() if k != "processed_match_ids"}
    print(json.dumps(summary, indent=2))
    print(f"Wrote {PROCESSED_DIR / 'shots.csv'}")


if __name__ == "__main__":
    main()
