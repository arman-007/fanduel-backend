# ─────────────────────────────────────────────
#  db.py  —  MongoDB client + index setup
# ─────────────────────────────────────────────
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.database import Database
from config import (
    MONGO_URI, DB_NAME,
    COL_COMPETITIONS, COL_FIXTURES, COL_PLAYER_ODDS, COL_INGESTION_LOG,
    COL_SEASONS, COL_TEAMS, COL_PLAYERS, COL_PREDICTIONS,
)

_client: MongoClient = None


def get_db() -> Database:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client[DB_NAME]


def ensure_indexes() -> None:
    """
    Create all indexes. Safe to call on every startup — MongoDB is idempotent.
    """
    db = get_db()

    # competitions
    db[COL_COMPETITIONS].create_index(
        [("competitionId", ASCENDING)], unique=True, name="uk_competition_id"
    )

    # fixtures
    db[COL_FIXTURES].create_index(
        [("fixtureId", ASCENDING)], unique=True, name="uk_fixture_id"
    )
    db[COL_FIXTURES].create_index(
        [("competitionId", ASCENDING)], name="idx_fixture_competition"
    )
    db[COL_FIXTURES].create_index(
        [("matchDate", ASCENDING)], name="idx_fixture_date"
    )

    # player_odds
    db[COL_PLAYER_ODDS].create_index(
        [("fixtureId", ASCENDING), ("selectionId", ASCENDING)],
        unique=True, name="uk_player_odds"
    )
    db[COL_PLAYER_ODDS].create_index(
        [("fixtureId", ASCENDING)], name="idx_po_fixture"
    )
    db[COL_PLAYER_ODDS].create_index(
        [("competitionId", ASCENDING)], name="idx_po_competition"
    )
    db[COL_PLAYER_ODDS].create_index(
        [("playerName", TEXT)], name="idx_po_player_text"
    )

    # ingestion_log
    db[COL_INGESTION_LOG].create_index(
        [("createdAt", DESCENDING)], name="idx_log_created"
    )
    db[COL_INGESTION_LOG].create_index(
        [("competitionId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_log_competition_created"
    )

    # seasons registry
    db[COL_SEASONS].create_index(
        [("sportinerdSeasonId", ASCENDING)], unique=True, name="uk_season_id"
    )
    db[COL_SEASONS].create_index(
        [("competitionId", ASCENDING), ("seasonYear", ASCENDING)],
        unique=True, name="uk_season_comp_year"
    )

    # teams registry
    db[COL_TEAMS].create_index(
        [("sportinerdTeamId", ASCENDING)], unique=True, name="uk_team_id"
    )
    db[COL_TEAMS].create_index(
        [("nameNormalised", ASCENDING)], name="idx_team_name"
    )
    db[COL_TEAMS].create_index(
        [("goalserveId", ASCENDING)],
        sparse=True, name="idx_team_goalserve"   # sparse: only docs where field exists
    )

    # players registry
    db[COL_PLAYERS].create_index(
        [("sportinerdPlayerId", ASCENDING)], unique=True, name="uk_player_id"
    )
    db[COL_PLAYERS].create_index(
        [("nameNormalised", ASCENDING)], name="idx_player_name"
    )
    db[COL_PLAYERS].create_index(
        [("goalserveId", ASCENDING)],
        sparse=True, name="idx_player_goalserve"
    )
    # TEXT index required for /api/registry/players?name= $text search
    db[COL_PLAYERS].create_index(
        [("name", TEXT), ("nameNormalised", TEXT)],
        name="idx_player_text"
    )

    # predictions
    db[COL_PREDICTIONS].create_index(
        [("fixtureId", ASCENDING)], unique=True, name="uk_prediction_fixture"
    )
    db[COL_PREDICTIONS].create_index(
        [("competitionId", ASCENDING)], name="idx_pred_competition"
    )
    db[COL_PREDICTIONS].create_index(
        [("snapshotAt", DESCENDING)], name="idx_pred_snapshot"
    )

    print("[db] Indexes ensured.")
