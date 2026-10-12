# FootStat

A locally running football analytics app that estimates **Expected Goals (xG)**: the probability that a shot becomes a goal. It is trained on real StatsBomb event data from the FIFA World Cup 2022.

- **Dashboard:** shots, goals, total predicted xG, goals vs xG by date, the top five players by xG, and the model's held-out evaluation.
- **Shot Map:** all 1,453 historical shots at their recorded pitch locations. Green marks a goal, red a non-goal, and marker size shows predicted xG. Filter by team, player or outcome, and click a shot for details.
- **Shot Predictor:** click a location, pick a body part, and the backend model returns a goal probability.

A two-minute walkthrough is in [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

## Architecture

```
StatsBomb Open Data (GitHub, JSON)
        │  scripts/build_shots_dataset.py
        ▼
data/processed/shots.csv ─── scripts/train_model.py ──► artifacts/model.joblib
        │                                                artifacts/metrics.json
        ▼                                                         │
FastAPI (backend/app) ◄───────── loaded once at startup ──────────┘
        │  /api/health  /api/overview  /api/shots  /api/predict  /api/metrics
        ▼
React + Vite frontend (frontend/) at http://localhost:5173
```

- **Frontend:** React 19, Vite 8, TypeScript, Tailwind CSS v4 (`@tailwindcss/vite`), Recharts, Lucide icons. The pitch is a custom SVG drawn in StatsBomb coordinates.
- **Backend:** Python 3.12, FastAPI + Uvicorn, pandas, NumPy, scikit-learn, joblib.
- **Model:** one scikit-learn logistic regression. Inputs are shot `x`, `y` and `body_part`; distance and angle to goal are calculated inside the saved pipeline.
- **Storage:** local CSV and JSON files only. There is no database, authentication or deployment.

```
xgenius/
├── frontend/                 React app (src/api, src/components, src/pages)
└── backend/
    ├── app/                  FastAPI: main.py, api/routes.py, schemas/, services/
    ├── data/raw/             Cached StatsBomb JSON (git-ignored)
    ├── data/processed/       shots.csv, matches.csv, shots_report.json (git-ignored)
    ├── artifacts/            model.joblib, metrics.json, evaluation_report.txt (git-ignored)
    ├── scripts/              build_shots_dataset.py, train_model.py
    ├── tests/                pytest: model artifact + API
    └── requirements.txt
```

## Setup (Windows PowerShell)

Requirements: **Python 3.12** (the `py` launcher) and **Node.js 20.19+ or 22.12+**.

These commands work in a default PowerShell window. They call the virtual environment's `python.exe` and `npm.cmd` directly, so PowerShell doesn't need permission to run scripts (no `Activate.ps1`, no `npm.ps1`). Run all commands from the `xgenius` project folder unless a step says otherwise.

### 1. Python environment

```powershell
py -3.12 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 2. Frontend dependencies

```powershell
cd frontend
npm.cmd install
cd ..
```

### 3. Data preprocessing

This downloads the 64 World Cup 2022 matches (about 17 MB compressed, cached in `backend\data\raw`) and writes `backend\data\processed\shots.csv`.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.build_shots_dataset
cd ..
```

### 4. Model training

This writes `backend\artifacts\model.joblib`, `metrics.json` and `evaluation_report.txt`.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.train_model
.\.venv\Scripts\python.exe -m pytest
cd ..
```

Steps 3 and 4 are only needed once. With the cached data they give byte-identical output on re-runs.

## Running the app

Use two PowerShell windows, both opened in the `xgenius` folder.

**Window 1: backend** (http://127.0.0.1:8000, API docs at `/docs`)

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000
```

**Window 2: frontend** (http://localhost:5173)

```powershell
cd frontend
npm.cmd run dev
```

Open http://localhost:5173. Check the backend at http://127.0.0.1:8000/api/health; it should report `"status": "ok"`. Stop either server with `Ctrl+C`.

The frontend calls `http://127.0.0.1:8000` by default. To change it, copy `frontend\.env.example` to `frontend\.env.local` and set `VITE_API_BASE_URL`.

> Prefer an activated environment? `.\backend\.venv\Scripts\Activate.ps1` and plain `npm` only work after allowing local scripts once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. The commands above don't need that.

## Data pipeline details

`scripts/build_shots_dataset.py` (options: `--competition-id`, `--season-id`, `--max-matches N`, `--refresh`):

- Only `Shot` events are used. Own goals are separate events and are never counted as shots.
- Penalty-shootout attempts (period 5, 41 shots) are excluded because they don't count toward the match score.
- Shots without a valid on-pitch location or a recognised outcome are excluded and counted in `shots_report.json`. None were found in this dataset.
- `goal` = 1 when the outcome is Goal. Saved, Blocked, Off T, Post, Wayward, Saved Off Target and Saved to Post are all 0.
- Coordinates use StatsBomb's 120 × 80 pitch: the attacking goal is at x = 120, with posts at y = 36 and 44. This was checked against the data.
- As a check, shot goals plus own goals equal the final score in all 64 matches (169 + 3 = 172).

Result: 1,453 shots, 169 goals and 1,284 non-goals, with no missing values.

## Model and evaluation

`scripts/train_model.py` trains a `LogisticRegression` (scaled numeric features, one-hot body part, no class re-weighting so the probabilities stay realistic). It is evaluated on **16 held-out matches** (378 shots, 42 goals), split by `match_id` with seed 42:

| Held-out metric | Model | Base rate (11.8% for every shot) | StatsBomb xG (benchmark) |
|---|---|---|---|
| Log loss ↓ | 0.2779 | 0.3491 | 0.2379 |
| Brier score ↓ | 0.0789 | 0.0988 | 0.0670 |
| ROC-AUC ↑ | 0.8085 | 0.5000 | 0.8649 |

The model beats the base rate on all three metrics but is weaker than StatsBomb's own xG, which also uses defender and goalkeeper positions and shot type. `statsbomb_xg` and the actual shot outcome are never model inputs. These figures come from `artifacts/metrics.json`, and the integration check recomputed them from the saved model.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Whether the model, dataset and metrics loaded. Returns 503 with the reasons if any are missing. |
| `GET /api/overview` | Totals, total predicted xG, top 5 players by xG, and goals and xG per match and per date. |
| `GET /api/shots` | Historical shots. Filters: `player`, `team` (case- and accent-insensitive substring), `outcome` (`goal` or `no_goal`), `match_id`. Paging: `limit` (default 500, max 2000) and `offset`. |
| `POST /api/predict` | `{"x": 0-120, "y": 0-80, "body_part": "Right Foot" \| "Left Foot" \| "Head" \| "Other"}` returns `predicted_xg`, `model_version`, `distance`, `angle` and `angle_degrees`. Invalid input returns 422. |
| `GET /api/metrics` | Held-out test metrics and the number of test examples. |

## Known limitations

- **Penalties are under-predicted.** Shot type isn't a model input, so a penalty is treated like an open-play shot from the spot: about 26% predicted, against 74% scored in this data.
- **Simple features.** Location and body part only. There's no defender, goalkeeper, assist or game-state information, so the model is clearly weaker than StatsBomb xG.
- **Small, single-tournament dataset.** 1,453 shots from one World Cup; the 42-goal test set makes the metrics noisy.
- **Historical xG includes training data.** Dashboard and shot-map xG totals cover the 48 training matches as well, so they describe the data rather than measure accuracy. Only `/api/metrics` is an out-of-sample evaluation.
- **Overlapping markers.** Twelve pitch locations hold more than one shot (mostly the penalty spot), and in dense areas a marker can hide one beneath it. Use the team or player filter to isolate a shot before clicking.
- **Predictor scope.** It lets you pick a spot in the attacking half only, which covers every shot in the training data.
- **Body-part list.** The frontend's body-part list is a copy of the backend's list rather than being fetched from the API.
- **Build size warning.** The production build warns about a bundle over 500 kB (mostly Recharts). It has no effect on running locally.

## Data attribution

Match and event data: [StatsBomb Open Data](https://github.com/statsbomb/open-data), made freely available by StatsBomb for research and football analytics projects. Per StatsBomb's terms, any published or shared work based on this data must credit **StatsBomb** as the source and use the StatsBomb logo from their [Media Pack](https://statsbomb.com/media-pack/). Raw and processed data aren't committed to this repository; regenerate them with step 3.
