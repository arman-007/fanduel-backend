# ─────────────────────────────────────────────
#  config.py  —  shared settings
#  All overrides live in .env — do not hard-code secrets here.
# ─────────────────────────────────────────────
import os
from dotenv import load_dotenv

load_dotenv()  # load .env from project root (or any parent dir)

# MongoDB — DB_URL takes priority (matches .env convention), falls back to MONGO_URI
MONGO_URI = os.getenv("DB_URL") or os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("DB_NAME", "fanduel-prediction")

# FanDuel source file — path to the JSON snapshot to ingest
FANDUEL_SOURCE = os.getenv("FANDUEL_SOURCE", "")

# Auth — single-user credentials for the internal dashboard
AUTH_EMAIL    = os.getenv("AUTH_EMAIL", "")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")
JWT_SECRET   = os.getenv("JWT_SECRET", "sportinerd-dev-secret-change-me")

# Collection names — existing
COL_COMPETITIONS  = "competitions"
COL_FIXTURES      = "fixtures"
COL_PLAYER_ODDS   = "player_odds"
COL_INGESTION_LOG = "ingestion_log"

# Collection names — new (registry + predictions)
COL_SEASONS     = "seasons"
COL_TEAMS       = "teams"
COL_PLAYERS     = "players"
COL_PREDICTIONS = "predictions"

# Snapshot retention (days) — snapshots older than this are deleted
SNAPSHOT_RETENTION_DAYS = 30

# FastAPI server
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ─── Market type → internal key mapping ─────
# Normalised markets (mutually exclusive runners — apply overround removal)
NORMALISED_MARKETS = {
    "OUTRIGHT_BETTING",
    "TO_REACH_THE_FINAL",
    "TOP_GOALSCORER",
    "WIN-DRAW-WIN",
    "CORRECT_SCORE",
}

# Player market type → JS key (raw probability — NOT normalised)
PLAYER_MARKET_MAP = {
    "TO_SCORE":                              "anytimeGoalscorer",
    "TO_SCORE_2_OR_MORE_GOALS":              "toScore2OrMore",
    "TO_SCORE_A_HAT-TRICK":                  "toScoreHatTrick",
    "ANYTIME_ASSIST":                        "anytimeAssist",
    "TO_SCORE_OR_ASSIST":                    "toScoreOrAssist",
    "GOALSCORER_ASSIST_DOUBLE":              "goalAssistDouble",
    "PLAYER_TO_HAVE_1_OR_MORE_SHOTS":        "shots1Plus",
    "PLAYER_TO_HAVE_2_OR_MORE_SHOTS":        "shots2Plus",
    "PLAYER_TO_HAVE_1_OR_MORE_SHOTS_ON_TARGET":  "shotsOnTarget1Plus",
    "PLAYER_TO_HAVE_2_OR_MORE_SHOTS_ON_TARGET":  "shotsOnTarget2Plus",
    "PLAYER_TO_HAVE_3_OR_MORE_SHOTS_ON_TARGET":  "shotsOnTarget3Plus",
}

# Tournament future type → field in competitions.tournamentOdds
TOURNAMENT_MARKET_MAP = {
    "OUTRIGHT_BETTING":    "champion",
    "TO_REACH_THE_FINAL":  "runnerUp",
    "TOP_GOALSCORER":      "topScorer",
}

# ─── Prediction model constants ──────────────────────────────────────────────
#
# SOT_GOAL_CONVERSION:
#   In UEFA Champions League, ~35% of shots on target become goals.
#   Source: UEFA technical reports 2022-24, range 33-37%, midpoint = 0.35
#   Used for: GK saves estimation (xG_against → expected SoT faced → expected saves)
#
# ASSIST_RATE:
#   ~78% of goals in European football have a credited assist.
#   Source: StatsBomb open data analysis, Opta 2023-24 season averages.
#   Used for: G+A combo derivation when GOALSCORER_ASSIST_DOUBLE market is absent.
#
# COMBO_TOP_SCORERS / COMBO_TOP_ASSISTERS:
#   Limit combo generation to top N players by probability.
#   40 scorers × 40 assisters = 1600 pairs — too much noise.
#   Top 10 × top 10 = 100 pairs, filter to top 20 by derived prob.
#
SOT_GOAL_CONVERSION   = float(0.35)
ASSIST_RATE           = float(0.78)
COMBO_TOP_SCORERS     = 10
COMBO_TOP_ASSISTERS   = 10
COMBO_TOP_OUTPUT      = 20   # max combo pairs stored per fixture
