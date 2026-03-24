#!/usr/bin/env python3
"""
api.py — Phase 3: FastAPI REST API
────────────────────────────────────
Run:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
    GET /api/competitions
    GET /api/fixtures?competition_id=228
    GET /api/tournament-odds?competition_id=228
    GET /api/match-odds?fixture_id=35314481
    GET /api/player-odds?fixture_id=35314481

CORS:
    Controlled by the CORS_ORIGINS environment variable.
    Set to a comma-separated list of allowed origins in production.
    Example: CORS_ORIGINS="https://odds.sportinerd.com,https://app.sportinerd.com"
    Defaults to localhost only when not set.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo.errors import ServerSelectionTimeoutError

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

from config import (
    COL_COMPETITIONS, COL_FIXTURES, COL_PLAYER_ODDS,
    COL_SEASONS, COL_TEAMS, COL_PLAYERS, COL_PREDICTIONS,
    API_HOST, API_PORT,
)
from db import get_db, ensure_indexes

# CORS origins: read from environment, safe default is localhost only
_cors_env = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]


# ═══════════════════════════════════════════════
#  APP SETUP
# ═══════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup logic once; FastAPI >= 0.93 lifespan pattern."""
    try:
        ensure_indexes()
        print("[api] Connected to MongoDB and indexes verified.")
    except ServerSelectionTimeoutError:
        print("[api] WARNING: MongoDB not reachable on startup — will retry on first request.")
    yield   # application runs here


app = FastAPI(
    title="Sportinerd Odds API",
    description="FanDuel odds data for Sportinerd platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════

def _clean(doc: Dict) -> Dict:
    """Remove MongoDB internal _id field from response."""
    doc.pop("_id", None)
    return doc


def _runner_response(r: Dict) -> Dict:
    """Shape a runner dict for API response — keep only fields the frontend uses."""
    return {
        "selectionId":          r.get("selectionId"),
        "name":                 r.get("name"),
        "logo":                 r.get("logo"),
        "americanOdds":         r.get("americanOdds"),
        "decimalOdds":          r.get("decimalOdds"),
        "rawProbability":       round(r.get("rawProbability", 0), 4),
        "normalizedProbability": round(r.get("normalizedProbability", r.get("rawProbability", 0)), 4),
        # correct score only
        **({"scoreHome": r["scoreHome"], "scoreAway": r["scoreAway"]}
           if "scoreHome" in r else {}),
        # WDW only
        **({"resultType": r["resultType"]} if "resultType" in r else {}),
    }


# ═══════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════

@app.get("/api/competitions", summary="List all competitions")
def get_competitions() -> List[Dict]:
    """
    Returns all competitions with fixture count.
    Response: [ { competitionId, name, fixtureCount } ]

    Single aggregation — counts all competition fixture totals in one round-trip.
    """
    db = get_db()
    comps = list(db[COL_COMPETITIONS].find({}, {"_id": 0, "competitionId": 1, "name": 1}))
    if not comps:
        return []

    # One aggregation to count fixtures per competition — no loop of queries
    pipeline = [
        {"$group": {"_id": "$competitionId", "count": {"$sum": 1}}}
    ]
    counts = {row["_id"]: row["count"] for row in db[COL_FIXTURES].aggregate(pipeline)}

    return [
        {
            "competitionId": c["competitionId"],
            "name":          c["name"],
            "fixtureCount":  counts.get(c["competitionId"], 0),
        }
        for c in comps
    ]


@app.get("/api/fixtures", summary="List fixtures for a competition")
def get_fixtures(competition_id: int = Query(..., description="Competition ID")) -> List[Dict]:
    """
    Returns all fixtures for a competition, sorted by matchDate ascending.
    Response: [ { fixtureId, name, homeTeam, awayTeam, matchDate } ]
    """
    db   = get_db()
    docs = list(
        db[COL_FIXTURES]
        .find(
            {"competitionId": competition_id},
            {"_id": 0, "fixtureId": 1, "name": 1, "homeTeam": 1, "awayTeam": 1, "matchDate": 1},
        )
        .sort("matchDate", 1)
    )
    return [
        {
            "fixtureId": d["fixtureId"],
            "name":      d["name"],
            "homeTeam":  d.get("homeTeam"),
            "awayTeam":  d.get("awayTeam"),
            "matchDate": d["matchDate"].isoformat() if isinstance(d.get("matchDate"), datetime) else d.get("matchDate"),
        }
        for d in docs
    ]


@app.get("/api/tournament-odds", summary="Tournament odds for a competition")
def get_tournament_odds(competition_id: int = Query(..., description="Competition ID")) -> Dict:
    """
    Returns champion, runnerUp, topScorer odds for a competition.
    runnerUpNote explains the TO_REACH_THE_FINAL proxy.
    Response: { competitionId, name, champion[], runnerUp[], topScorer[], runnerUpNote, snapshotAt }
    """
    db  = get_db()
    doc = db[COL_COMPETITIONS].find_one({"competitionId": competition_id}, {"_id": 0})

    if not doc:
        raise HTTPException(status_code=404, detail=f"Competition {competition_id} not found")

    t = doc.get("tournamentOdds", {})

    def shape_runners(runners: List[Dict]) -> List[Dict]:
        return [
            {
                "selectionId":           r.get("selectionId"),
                "name":                  r.get("name"),
                "logo":                  r.get("logo"),
                "americanOdds":          r.get("americanOdds"),
                "decimalOdds":           r.get("decimalOdds"),
                "rawProbability":        round(r.get("rawProbability", 0), 4),
                "probability":           round(r.get("normalizedProbability", r.get("rawProbability", 0)), 4),
            }
            for r in (runners or [])
        ]

    snap = doc.get("snapshotAt")
    return {
        "competitionId": competition_id,
        "name":          doc.get("name"),
        "champion":      shape_runners(t.get("champion", [])),
        "runnerUp":      shape_runners(t.get("runnerUp", [])),
        "topScorer":     shape_runners(t.get("topScorer", [])),
        "runnerUpNote":  (
            "Runner-up odds are sourced from the 'To Reach The Final' market "
            "as FanDuel does not offer a standalone runner-up outright for this competition."
        ),
        "snapshotAt": snap.isoformat() if isinstance(snap, datetime) else snap,
    }


@app.get("/api/match-odds", summary="Win/Draw/Win and Correct Score for a fixture")
def get_match_odds(fixture_id: int = Query(..., description="Fixture (event) ID")) -> Dict:
    """
    Returns WDW and Correct Score odds for a single fixture.
    All probabilities are normalised (bookmaker margin removed).
    Response: { fixtureId, name, homeTeam, awayTeam, wdw[], correctScore[] }
    """
    db  = get_db()
    doc = db[COL_FIXTURES].find_one({"fixtureId": fixture_id}, {"_id": 0})

    if not doc:
        raise HTTPException(status_code=404, detail=f"Fixture {fixture_id} not found")

    mo = doc.get("matchOdds", {})

    def shape_wdw(runners: List[Dict]) -> List[Dict]:
        return [
            {
                "selectionId": r.get("selectionId"),
                "name":        r.get("name"),
                "resultType":  r.get("resultType"),
                "probability": round(r.get("normalizedProbability", r.get("rawProbability", 0)), 4),
                "americanOdds": r.get("americanOdds"),
                "decimalOdds":  r.get("decimalOdds"),
            }
            for r in (runners or [])
        ]

    def shape_cs(runners: List[Dict]) -> List[Dict]:
        return [
            {
                "selectionId": r.get("selectionId"),
                "name":        r.get("name"),
                "scoreHome":   r.get("scoreHome"),
                "scoreAway":   r.get("scoreAway"),
                "probability": round(r.get("normalizedProbability", r.get("rawProbability", 0)), 4),
                "americanOdds": r.get("americanOdds"),
                "decimalOdds":  r.get("decimalOdds"),
            }
            for r in (runners or [])
        ]

    match_date = doc.get("matchDate")
    return {
        "fixtureId":    fixture_id,
        "name":         doc.get("name"),
        "homeTeam":     doc.get("homeTeam"),
        "awayTeam":     doc.get("awayTeam"),
        "matchDate":    match_date.isoformat() if isinstance(match_date, datetime) else match_date,
        "wdw":          shape_wdw(mo.get("wdw", [])),
        "correctScore": shape_cs(mo.get("correctScore", [])),
    }


@app.get("/api/player-odds", summary="Player market odds for a fixture")
def get_player_odds(fixture_id: int = Query(..., description="Fixture (event) ID")) -> List[Dict]:
    """
    Returns all player market odds for a fixture.
    Player binary markets use raw probability (not normalised).
    G+A Double entries have playerName = 'Scorer to score a goal assisted by Assister'.
    Response: [ { selectionId, playerName, logo, markets: { key: prob } } ]
    """
    db   = get_db()
    docs = list(
        db[COL_PLAYER_ODDS]
        .find({"fixtureId": fixture_id}, {"_id": 0})
        .sort("playerName", 1)
    )

    return [
        {
            "selectionId": d.get("selectionId"),
            "playerName":  d.get("playerName"),
            "logo":        d.get("logo"),
            "markets":     {k: round(v, 4) for k, v in d.get("markets", {}).items()},
        }
        for d in docs
    ]


@app.get("/api/predictions", summary="Derived predictions for a fixture")
def get_predictions(fixture_id: int = Query(..., description="Fixture (event) ID")) -> Dict:
    """
    Returns computed predictions for a fixture.
    All predictions carry 'source' and 'method' fields:
      source: "feed"    → derived directly from FanDuel market data
      source: "derived" → computed by internal model (see method for assumptions)

    Methods:
      cs_matrix               — exact derivation from Correct Score matrix
      poisson_xg              — Poisson model from xG (GK saves)
      independence_approximation — G+A combo when feed data absent

    Response: {
      fixtureId, homeTeam, awayTeam,
      match: { homeCleanSheet, awayCleanSheet, btts, xGHome, xGAway, overUnder },
      gkSaves: [ { teamSide, teamName, prob3Plus, xGAgainst, source, method, assumptions } ],
      combos: { source, note, pairs: [ { scorerName, assisterName, probability, source, method } ] }
    }
    """
    db  = get_db()
    doc = db[COL_PREDICTIONS].find_one({"fixtureId": fixture_id}, {"_id": 0})

    if not doc:
        raise HTTPException(status_code=404, detail=f"No predictions for fixture {fixture_id}")

    snap = doc.get("snapshotAt")
    return {
        "fixtureId":  fixture_id,
        "sportinerdFixtureId": doc.get("sportinerdFixtureId"),
        "homeTeam":   doc.get("homeTeam"),
        "awayTeam":   doc.get("awayTeam"),
        "match":      doc.get("match", {}),
        "gkSaves":    doc.get("gkSaves", []),
        "combos":     doc.get("combos", {}),
        "snapshotAt": snap.isoformat() if isinstance(snap, datetime) else snap,
    }


@app.get("/api/registry/teams", summary="Internal team registry")
def get_teams() -> List[Dict]:
    """All teams with their sportinerdTeamId and goalserveId slot."""
    db = get_db()
    docs = list(db[COL_TEAMS].find({}, {"_id": 0}).sort("name", 1))
    return docs


@app.get("/api/registry/players", summary="Internal player registry")
def get_players(name: Optional[str] = Query(None, description="Filter by name (partial match)")) -> List[Dict]:
    """All players with their sportinerdPlayerId and goalserveId slot."""
    db = get_db()
    # Truncate to 200 chars — $text search is injection-safe but unbounded input causes slow queries
    safe_name = name[:200].strip() if name else None
    query = {"$text": {"$search": safe_name}} if safe_name else {}
    docs  = list(db[COL_PLAYERS].find(query, {"_id": 0}).sort("name", 1).limit(200))
    return docs


# ═══════════════════════════════════════════════
#  HEALTH CHECK
# ═══════════════════════════════════════════════

@app.get("/health", include_in_schema=False)
def health():
    try:
        get_db().command("ping")
        return {"status": "ok", "db": "connected", "ts": datetime.now(tz=timezone.utc).isoformat()}
    except Exception as e:
        return {"status": "degraded", "db": str(e), "ts": datetime.now(tz=timezone.utc).isoformat()}


# ═══════════════════════════════════════════════
#  FRONTEND — serve built React app
#  Mount static assets then catch all remaining
#  paths so React Router (or tab state) works.
#  Only active when `frontend/dist` has been built.
# ═══════════════════════════════════════════════

if FRONTEND_DIST.is_dir():
    _assets = FRONTEND_DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="static_assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str = ""):
        # Serve any real file inside dist (e.g. favicon, manifest)
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        # Everything else → index.html (SPA entry point)
        return FileResponse(str(FRONTEND_DIST / "index.html"))


# ═══════════════════════════════════════════════
#  ENTRYPOINT
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host=API_HOST, port=API_PORT, reload=True)
