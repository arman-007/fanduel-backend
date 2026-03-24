# ─────────────────────────────────────────────────────────────────────────────
#  ids.py  —  deterministic internal ID generation (UUID5)
#
#  WHY UUID5:
#    Same input → same UUID, every time.
#    "Bayern Munich" always gets the same sportinerdTeamId regardless of
#    which file or ingest run created it. This makes cross-source mapping
#    (e.g. Goalserve) trivial — just populate goalserveId once and it sticks.
#
#  HIERARCHY:
#    Season  → scoped to competition + calendar year
#    Team    → global (not season-scoped) — Bayern Munich is always Bayern Munich
#    Player  → global — Harry Kane is always Harry Kane
#    Fixture → scoped to homeTeam + awayTeam + season
# ─────────────────────────────────────────────────────────────────────────────

import re
import uuid
from datetime import datetime

# Fixed namespace UUID — unique to Sportinerd, never changes
_NS = uuid.UUID("7f3a9b2c-d15e-4f8a-b6c3-921847560def")


# ── Slug helper ───────────────────────────────────────────────────────────────

def slug(name: str) -> str:
    """
    Normalise a name to a stable lowercase slug for UUID generation.
    "Bayern Munich" → "bayern_munich"
    "Paris St-G"    → "paris_st_g"
    """
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


# ── Season detection ──────────────────────────────────────────────────────────

def detect_season(dt: datetime) -> str:
    """
    Infer season year string from a match date.
    Football season starts in July:
      openDate 2025-08-xx → "2025-26"
      openDate 2026-03-xx → "2025-26"
    """
    if dt.month >= 7:
        return f"{dt.year}-{str(dt.year + 1)[2:]}"
    return f"{dt.year - 1}-{str(dt.year)[2:]}"


# ── ID generators ─────────────────────────────────────────────────────────────

def make_season_id(competition_id: int, season_year: str) -> str:
    """
    UUID5 from competition_id + season_year.
    Example: competition 228, season "2025-26" → stable UUID.
    """
    return str(uuid.uuid5(_NS, f"season:{competition_id}:{season_year}"))


def make_team_id(name: str) -> str:
    """
    UUID5 from normalised team name. Global — not season-scoped.
    "Bayern Munich" → same ID forever.
    """
    return str(uuid.uuid5(_NS, f"team:{slug(name)}"))


def make_player_id(name: str) -> str:
    """
    UUID5 from normalised player name. Global — not season-scoped.
    "Harry Kane" → same ID forever.
    Raises ValueError if name is empty — callers must guard before calling.
    """
    if not name or not name.strip():
        raise ValueError("make_player_id requires a non-empty player name")
    return str(uuid.uuid5(_NS, f"player:{slug(name)}"))


def make_fixture_id(home_team_id: str, away_team_id: str, season_id: str) -> str:
    """
    UUID5 from homeTeamId + awayTeamId + seasonId.
    Stable: same fixture in same season always gets the same ID.
    """
    return str(uuid.uuid5(_NS, f"fixture:{home_team_id}:{away_team_id}:{season_id}"))


# ── Registry doc builders ──────────────────────────────────────────────────────

def season_doc(competition_id: int, competition_name: str, season_year: str, now: datetime) -> dict:
    return {
        "sportinerdSeasonId": make_season_id(competition_id, season_year),
        "competitionId":      competition_id,
        "competitionName":    competition_name,
        "seasonYear":         season_year,
        "goalserveId":        None,   # populated later when Goalserve mapping is ready
        "updatedAt":          now,
    }


def team_doc(name: str, now: datetime) -> dict:
    return {
        "sportinerdTeamId": make_team_id(name),
        "name":             name,
        "nameNormalised":   slug(name),
        "goalserveId":      None,
        "updatedAt":        now,
    }


def player_doc(name: str, now: datetime) -> dict:
    return {
        "sportinerdPlayerId": make_player_id(name),
        "name":               name,
        "nameNormalised":     slug(name),
        "goalserveId":        None,
        "updatedAt":          now,
    }
