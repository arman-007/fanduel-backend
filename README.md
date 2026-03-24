# Sportinerd Odds Explorer

Football odds ingestion, prediction, and visualization pipeline for the Sportinerd platform. Ingests FanDuel JSON snapshots, normalizes odds (removes bookmaker overround), computes match predictions, stores everything in MongoDB, and serves it via a FastAPI REST API with a React dashboard.

---

## Architecture

```
FanDuel JSON (all_league_data.json)
        │
        ▼
    ingest.py  ──── odds.py / ids.py / predictions.py
        │
        ▼
    MongoDB (fanduel-prediction)
        │
        ▼
    api.py  (FastAPI, port 8000)
        │
        ▼
    frontend/  (React + Vite)
```

The pipeline flows in one direction. `ingest.py` is the **only write path** to the database. The API and frontend are strictly read-only.

---

## Stack

- **Python 3.10+** — FastAPI, PyMongo, ijson, python-dotenv
- **MongoDB** — remote instance (connection string in `.env`)
- **React 18 + Vite** — SPA frontend served by the API in production

---

## Project Structure

```
test/
├── ingest.py         ETL pipeline: parse → upsert → purge → log
├── api.py            FastAPI REST layer + SPA serving
├── predictions.py    Prediction engine (cs_matrix, poisson_xg, independence_approximation)
├── odds.py           Decimal odds → raw probability → normalized probability
├── ids.py            Deterministic UUID5 ID generators
├── db.py             MongoDB client + index setup
├── config.py         Constants, collection names, env var loading
├── requirements.txt  Python dependencies
├── .env              Secrets and paths (not committed)
├── frontend/         React + Vite SPA
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api/client.js
│   │   ├── hooks/useApi.js
│   │   ├── utils/prob.js
│   │   └── components/tabs/
│   │       ├── TournamentTab.jsx
│   │       ├── MatchTab.jsx
│   │       ├── PlayersTab.jsx
│   │       └── PredictionsTab.jsx
│   ├── vite.config.js
│   └── package.json
└── PRD.md            Original product requirements document
```

---

## Setup

### 1. Python environment

```bash
cd /home/noob/Desktop/sportinerd/test
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment variables

Create a `.env` file (already present — do not commit):

```env
DB_URL=mongodb://<user>:<password>@<host>:27017/?authSource=<db>
DB_NAME=fanduel-prediction
FANDUEL_SOURCE=/home/noob/Desktop/sportinerd/fanduel/all_league_data.json
```

### 3. Frontend (production build)

```bash
cd frontend
npm install
npm run build   # outputs to frontend/dist/
```

The API automatically serves `frontend/dist/` when it exists.

---

## Running

### API server

```bash
source venv/bin/activate
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
# or: python api.py
```

Open `http://localhost:8000` in the browser.

### Frontend dev server (hot reload)

```bash
cd frontend
npm run dev   # runs on port 5173, proxies /api to localhost:8000
```

---

## Ingestion

The source JSON file is a large array of competition objects. It is streamed one competition at a time via `ijson` — the full file is never loaded into RAM.

```bash
# Dry run — parse only, no DB writes
python ingest.py --dry-run

# Full ingest (uses FANDUEL_SOURCE from .env)
python ingest.py

# Override source file
python ingest.py --file /path/to/other.json
```

### Scheduling

The FanDuel scraper runs daily at 08:00. Ingest is scheduled 6 hours later:

```cron
0 14 * * * PYTHONUNBUFFERED=1 /home/noob/Desktop/sportinerd/test/venv/bin/python /home/noob/Desktop/sportinerd/test/ingest.py >> /home/noob/Desktop/sportinerd/test/ingest.log 2>&1
```

---

## API Endpoints

Base URL: `http://localhost:8000`

| Method | Path | Query Params | Description |
|--------|------|-------------|-------------|
| GET | `/api/competitions` | — | All competitions with fixture count |
| GET | `/api/fixtures` | `competition_id` | Fixtures for a competition, sorted by date |
| GET | `/api/tournament-odds` | `competition_id` | Champion / RunnerUp / TopScorer odds |
| GET | `/api/match-odds` | `fixture_id` | WDW + Correct Score for a fixture |
| GET | `/api/player-odds` | `fixture_id` | All player market probabilities for a fixture |
| GET | `/api/predictions` | `fixture_id` | Computed predictions for a fixture |
| GET | `/api/registry/teams` | — | Internal team registry |
| GET | `/api/registry/players` | `name` (optional) | Player registry with name search |
| GET | `/health` | — | MongoDB ping health check |

Interactive docs: `http://localhost:8000/docs`

---

## MongoDB Collections

| Collection | Unique Key | Description |
|---|---|---|
| `competitions` | `competitionId` | Competition + tournament odds snapshot |
| `fixtures` | `fixtureId` | Per-fixture match odds (WDW + CS) |
| `player_odds` | `(fixtureId, selectionId)` | Per-player market probabilities |
| `predictions` | `fixtureId` | Derived predictions (xG, BTTS, CS, GK saves, G+A combos) |
| `seasons` | `sportinerdSeasonId` | Season registry |
| `teams` | `sportinerdTeamId` | Team registry |
| `players` | `sportinerdPlayerId` | Player registry |
| `ingestion_log` | `createdAt` | Run audit trail |

---

## Prediction Engine

All predictions are computed at ingest time in `predictions.py`. Nothing is computed in the API layer.

| Method | Confidence | Description |
|---|---|---|
| `cs_matrix` | HIGH | Exact derivation from the Correct Score probability matrix |
| `poisson_xg` | MEDIUM | GK saves estimate via Poisson model using xG |
| `independence_approximation` | LOW | G+A combo fallback when `GOALSCORER_ASSIST_DOUBLE` market is absent from the feed |

Every prediction document carries explicit `source`, `method`, and `assumptions` fields.

---

## Odds Normalisation

```
rawProbability     = 1 / decimalOdds × 100
overround          = sum(rawProbabilities) / 100
normalizedProb     = rawProbability / overround
```

Applied to mutually exclusive markets (Win/Draw/Win, Correct Score, tournament outrights). Player binary markets (anytime scorer, assist, shots) use `rawProbability` — normalisation is not meaningful for independent binary events.

---

## Internal IDs

All IDs are deterministic UUID5 values derived from a fixed namespace. The same input always produces the same ID across re-ingestions, making upserts safe and idempotent.

| ID | Seed |
|---|---|
| `sportinerdSeasonId` | `competition_id:season_year` |
| `sportinerdTeamId` | `team_name_normalised` |
| `sportinerdPlayerId` | `player_name_normalised` |
| `sportinerdFixtureId` | `home_team_id:away_team_id:season_id` |

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `DB_URL` | — | MongoDB connection string (required) |
| `DB_NAME` | `fanduel-prediction` | Database name |
| `FANDUEL_SOURCE` | — | Path to the FanDuel JSON source file |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated allowed origins |
| `API_HOST` | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI port |
