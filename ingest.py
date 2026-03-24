#!/usr/bin/env python3
"""
ingest.py — FanDuel JSON ingestion (v3)
─────────────────────────────────────────────────────────────────────────────
Usage:
    python ingest.py                          # uses FANDUEL_SOURCE from .env
    python ingest.py --file path/to/file.json # override source file
    python ingest.py --dry-run                # parse only, no DB writes

Supports two input formats:
    • JSON array  [ {...competition...}, {...}, ... ]  ← all_league_data.json
    • JSON object { "competitionId": ..., ... }        ← single-competition file

For arrays the file is streamed one competition at a time via ijson — the full
163 MB (or larger) file is never loaded into RAM all at once.

Pipeline per competition:
    1.  Stream / load competition object
    2.  Convert decimal odds → raw probability → normalised probability
    3.  Generate deterministic UUID5 IDs for all entities
    4.  Upsert registries: seasons, teams, players
    5.  Upsert core data: competitions, fixtures, player_odds
    6.  Compute predictions at ingest time, upsert predictions collection
    7.  (After all competitions) purge snapshots older than SNAPSHOT_RETENTION_DAYS
    8.  Write single summary ingestion_log entry
"""

import argparse
import decimal
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import ijson
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from config import (
    PLAYER_MARKET_MAP, TOURNAMENT_MARKET_MAP,
    SNAPSHOT_RETENTION_DAYS, FANDUEL_SOURCE,
    COL_COMPETITIONS, COL_FIXTURES, COL_PLAYER_ODDS, COL_INGESTION_LOG,
    COL_SEASONS, COL_TEAMS, COL_PLAYERS, COL_PREDICTIONS,
)
from db import get_db, ensure_indexes
from odds import build_runner_base, normalise
from ids import (
    detect_season, make_season_id, make_team_id, make_player_id, make_fixture_id,
    season_doc, team_doc, player_doc,
)
from predictions import build_predictions

COMBO_RE = re.compile(r"^(.+?) to score a goal assisted by (.+)$", re.IGNORECASE)


# ─── odds helpers ─────────────────────────────────────────────────────────────

def build_tournament_runners(runners):
    built = [build_runner_base(r) for r in runners if r.get("runnerStatus") == "ACTIVE"]
    normalise(built)
    built.sort(key=lambda x: x.get("normalizedProbability", 0), reverse=True)
    return built

def build_wdw_runners(runners):
    ORDER = {"HOME": 0, "DRAW": 1, "AWAY": 2}
    built = []
    for r in runners:
        if r.get("runnerStatus") != "ACTIVE":
            continue
        base = build_runner_base(r)
        base["resultType"] = r.get("result", {}).get("type", "")
        built.append(base)
    normalise(built)
    built.sort(key=lambda x: ORDER.get(x["resultType"], 99))
    return built

def build_correct_score_runners(runners):
    built = []
    for r in runners:
        if r.get("runnerStatus") != "ACTIVE":
            continue
        result = r.get("result", {})
        if result.get("type") != "SCORE":
            continue
        base = build_runner_base(r)
        base["scoreHome"] = result.get("scoreHome")
        base["scoreAway"] = result.get("scoreAway")
        built.append(base)
    normalise(built)
    return built

def derive_teams(event):
    for market in event.get("futures", []):
        if market["marketType"] == "WIN-DRAW-WIN":
            home = away = None
            for r in market["runners"]:
                rt = r.get("result", {}).get("type")
                if rt == "HOME":
                    home = r.get("runnerName")
                elif rt == "AWAY":
                    away = r.get("runnerName")
            return home, away
    return None, None


# ─── parse ────────────────────────────────────────────────────────────────────

def parse(raw, snapshot_at):
    errors = []
    competition_id   = raw.get("competitionId")
    competition_name = raw.get("name", "Unknown")

    # Detect season from first event openDate
    first_date = snapshot_at
    for ev in raw.get("events", []):
        od = ev.get("openDate")
        if od:
            try:
                first_date = datetime.fromisoformat(od.replace("Z", "+00:00"))
            except Exception:
                pass
            break

    season_year     = detect_season(first_date)
    season_id       = make_season_id(competition_id, season_year)
    this_season_doc = season_doc(competition_id, competition_name, season_year, snapshot_at)

    # Tournament odds
    tournament_odds = {}
    for fut in raw.get("futures", []):
        mt    = fut["marketType"]
        field = TOURNAMENT_MARKET_MAP.get(mt)
        if field:
            tournament_odds[field] = build_tournament_runners(fut["runners"])

    competition_doc = {
        "competitionId":      competition_id,
        "sportinerdSeasonId": season_id,
        "name":               competition_name,
        "source":             "fanduel",
        "tournamentOdds":     tournament_odds,
        "snapshotAt":         snapshot_at,
        "updatedAt":          snapshot_at,
    }

    fixtures            = []
    player_ops          = []
    team_docs_map       = {}
    player_docs_map     = {}
    fixture_combo_flags = {}

    for event in raw.get("events", []):
        fixture_id = event.get("eventId")
        name       = event.get("name", "")

        od = event.get("openDate")
        match_date = None
        if od:
            try:
                match_date = datetime.fromisoformat(od.replace("Z", "+00:00"))
            except Exception:
                errors.append(f"[{fixture_id}] Could not parse openDate '{od}' — fixture skipped")
        if match_date is None:
            if not od:
                errors.append(f"[{fixture_id}] Missing openDate — fixture skipped")
            continue

        home_name, away_name = derive_teams(event)
        if not home_name or not away_name:
            errors.append(f"[{fixture_id}] Skipped — could not derive team names from WIN-DRAW-WIN market")
            continue

        home_team_id = make_team_id(home_name) if home_name else None
        away_team_id = make_team_id(away_name) if away_name else None
        fixture_sid  = make_fixture_id(home_team_id, away_team_id, season_id) if home_team_id else None

        for tname, tid in [(home_name, home_team_id), (away_name, away_team_id)]:
            if tname and tid and tid not in team_docs_map:
                team_docs_map[tid] = team_doc(tname, snapshot_at)

        wdw_runners    = []
        cs_runners     = []
        player_map     = {}
        has_combo_feed = False

        for market in event.get("futures", []):
            mt = market["marketType"]

            if mt == "WIN-DRAW-WIN":
                wdw_runners = build_wdw_runners(market["runners"])
            elif mt == "CORRECT_SCORE":
                cs_runners = build_correct_score_runners(market["runners"])
            elif mt in PLAYER_MARKET_MAP:
                market_key = PLAYER_MARKET_MAP[mt]

                if mt == "GOALSCORER_ASSIST_DOUBLE":
                    has_combo_feed = True

                for runner in market["runners"]:
                    if runner.get("runnerStatus") != "ACTIVE":
                        continue

                    sel_id = runner.get("selectionId")
                    if sel_id is None:
                        errors.append(f"[{fixture_id}] Runner with no selectionId in market {mt} — skipped")
                        continue

                    base = build_runner_base(runner)

                    if not base.get("name"):
                        errors.append(f"[{fixture_id}] Runner {sel_id} in market {mt} has no name — skipped")
                        continue

                    if mt == "GOALSCORER_ASSIST_DOUBLE":
                        key = f"combo_{sel_id}"
                        if key not in player_map:
                            player_map[key] = {
                                "selectionId":        sel_id,
                                "sportinerdPlayerId": None,
                                "playerName":         base["name"],
                                "logo":               base.get("logo"),
                                "markets":            {},
                            }
                        player_map[key]["markets"][market_key] = round(base["rawProbability"], 4)
                    else:
                        player_sid = make_player_id(base["name"])
                        if sel_id not in player_map:
                            player_map[sel_id] = {
                                "selectionId":        sel_id,
                                "sportinerdPlayerId": player_sid,
                                "playerName":         base["name"],
                                "logo":               base.get("logo"),
                                "markets":            {},
                            }
                        player_map[sel_id]["markets"][market_key] = round(base["rawProbability"], 4)

                        if player_sid not in player_docs_map:
                            player_docs_map[player_sid] = player_doc(base["name"], snapshot_at)

        fixture_combo_flags[fixture_id] = has_combo_feed

        fixtures.append({
            "fixtureId":            fixture_id,
            "sportinerdFixtureId":  fixture_sid,
            "sportinerdSeasonId":   season_id,
            "competitionId":        competition_id,
            "name":                 name,
            "homeTeam":             home_name,
            "awayTeam":             away_name,
            "homeTeamId":           home_team_id,
            "awayTeamId":           away_team_id,
            "matchDate":            match_date,
            "matchOdds":            {"wdw": wdw_runners, "correctScore": cs_runners},
            "snapshotAt":           snapshot_at,
            "updatedAt":            snapshot_at,
        })
        player_ops.append((fixture_id, competition_id, list(player_map.values())))

    return {
        "competition":         competition_doc,
        "season_doc":          this_season_doc,
        "team_docs":           list(team_docs_map.values()),
        "player_docs":         list(player_docs_map.values()),
        "fixtures":            fixtures,
        "player_ops":          player_ops,
        "fixture_combo_flags": fixture_combo_flags,
        "errors":              errors,
    }


# ─── compute predictions ──────────────────────────────────────────────────────

def compute_all_predictions(parsed):
    player_lookup = {fid: players for fid, _, players in parsed["player_ops"]}
    predictions   = []
    for fixture in parsed["fixtures"]:
        fid       = fixture["fixtureId"]
        players   = player_lookup.get(fid, [])
        has_combo = parsed["fixture_combo_flags"].get(fid, False)
        predictions.append(build_predictions(fixture, players, has_combo_feed=has_combo))
    return predictions


# ─── upsert (no purge — purge runs once after all competitions) ───────────────

def upsert(parsed, predictions, snapshot_at, dry_run=False):
    counts = {k: 0 for k in [
        "seasons_upserted", "teams_upserted", "players_upserted",
        "competitions_upserted", "fixtures_upserted",
        "player_docs_upserted", "predictions_upserted",
    ]}

    if dry_run:
        counts["fixtures_upserted"]    = len(parsed["fixtures"])
        counts["player_docs_upserted"] = sum(len(p[2]) for p in parsed["player_ops"])
        counts["predictions_upserted"] = len(predictions)
        return counts

    db = get_db()

    # 1. Season
    sd = parsed["season_doc"]
    db[COL_SEASONS].update_one(
        {"sportinerdSeasonId": sd["sportinerdSeasonId"]},
        {"$set": {"competitionName": sd["competitionName"], "updatedAt": snapshot_at},
         "$setOnInsert": {k: sd[k] for k in ["sportinerdSeasonId","competitionId","seasonYear","goalserveId"]}
                         | {"createdAt": snapshot_at}},
        upsert=True,
    )
    counts["seasons_upserted"] = 1

    # 2. Teams
    if parsed["team_docs"]:
        ops = [UpdateOne(
            {"sportinerdTeamId": t["sportinerdTeamId"]},
            {"$set": {"updatedAt": snapshot_at},
             "$setOnInsert": {k: t[k] for k in ["sportinerdTeamId","name","nameNormalised","goalserveId"]}
                              | {"createdAt": snapshot_at}},
            upsert=True,
        ) for t in parsed["team_docs"]]
        r = db[COL_TEAMS].bulk_write(ops, ordered=False)
        counts["teams_upserted"] = r.upserted_count + r.modified_count

    # 3. Players
    if parsed["player_docs"]:
        ops = [UpdateOne(
            {"sportinerdPlayerId": p["sportinerdPlayerId"]},
            {"$set": {"updatedAt": snapshot_at},
             "$setOnInsert": {k: p[k] for k in ["sportinerdPlayerId","name","nameNormalised","goalserveId"]}
                              | {"createdAt": snapshot_at}},
            upsert=True,
        ) for p in parsed["player_docs"]]
        r = db[COL_PLAYERS].bulk_write(ops, ordered=False)
        counts["players_upserted"] = r.upserted_count + r.modified_count

    # 4. Competition
    comp = parsed["competition"]
    db[COL_COMPETITIONS].update_one(
        {"competitionId": comp["competitionId"]},
        {"$set": {k: comp[k] for k in ["name","sportinerdSeasonId","source","tournamentOdds","snapshotAt","updatedAt"]},
         "$setOnInsert": {"createdAt": snapshot_at}},
        upsert=True,
    )
    counts["competitions_upserted"] = 1

    # 5. Fixtures
    if parsed["fixtures"]:
        ops = [UpdateOne(
            {"fixtureId": fix["fixtureId"]},
            {"$set": {k: fix[k] for k in [
                "sportinerdFixtureId","sportinerdSeasonId","competitionId",
                "name","homeTeam","awayTeam","homeTeamId","awayTeamId",
                "matchDate","matchOdds","snapshotAt","updatedAt"
            ]},
             "$setOnInsert": {"createdAt": snapshot_at}},
            upsert=True,
        ) for fix in parsed["fixtures"]]
        r = db[COL_FIXTURES].bulk_write(ops, ordered=False)
        counts["fixtures_upserted"] = r.upserted_count + r.modified_count

    # 6. Player odds
    all_ops = []
    for fid, comp_id, players in parsed["player_ops"]:
        for p in players:
            all_ops.append(UpdateOne(
                {"fixtureId": fid, "selectionId": p["selectionId"]},
                {"$set": {
                    "sportinerdPlayerId": p.get("sportinerdPlayerId"),
                    "competitionId": comp_id,
                    "playerName": p["playerName"],
                    "logo": p.get("logo"),
                    "markets": p["markets"],
                    "snapshotAt": snapshot_at,
                    "updatedAt": snapshot_at,
                },
                 "$setOnInsert": {"createdAt": snapshot_at}},
                upsert=True,
            ))
    if all_ops:
        try:
            r = db[COL_PLAYER_ODDS].bulk_write(all_ops, ordered=False)
            counts["player_docs_upserted"] = r.upserted_count + r.modified_count
        except BulkWriteError as e:
            print(f"[WARN] BulkWriteError: {e.details.get('writeErrors','')}")

    # 7. Predictions
    if predictions:
        ops = [UpdateOne(
            {"fixtureId": pred["fixtureId"]},
            {"$set": {k: pred[k] for k in [
                "sportinerdFixtureId","competitionId","homeTeam","awayTeam",
                "match","gkSaves","combos","snapshotAt","updatedAt"
            ]},
             "$setOnInsert": {"createdAt": snapshot_at}},
            upsert=True,
        ) for pred in predictions]
        r = db[COL_PREDICTIONS].bulk_write(ops, ordered=False)
        counts["predictions_upserted"] = r.upserted_count + r.modified_count

    return counts


# ─── purge (runs once after all competitions are ingested) ────────────────────

def purge_stale(snapshot_at):
    """Remove data older than SNAPSHOT_RETENTION_DAYS. Called once per run."""
    db     = get_db()
    cutoff = snapshot_at - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    purged  = db[COL_PLAYER_ODDS].delete_many({"snapshotAt": {"$lt": cutoff}}).deleted_count
    purged += db[COL_FIXTURES].delete_many(   {"matchDate":  {"$lt": cutoff}}).deleted_count
    purged += db[COL_PREDICTIONS].delete_many({"snapshotAt": {"$lt": cutoff}}).deleted_count
    return purged


# ─── streaming helpers ────────────────────────────────────────────────────────

def _first_byte(file_path):
    """Return the first non-whitespace byte of a file to detect array vs object."""
    with open(file_path, "rb") as f:
        while True:
            ch = f.read(1)
            if not ch:
                return b""
            if ch.strip():
                return ch


def _decimals_to_float(obj):
    """Recursively convert decimal.Decimal values (produced by ijson) to float."""
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimals_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimals_to_float(v) for v in obj]
    return obj


def iter_competitions(file_path):
    """
    Yield one competition dict at a time from file_path.
    Handles both:
      - JSON array  [{ ... }, { ... }]  → streamed via ijson (memory efficient)
      - JSON object { ... }             → loaded once (backward compat)
    """
    first = _first_byte(file_path)

    if first == b"[":
        # Large multi-competition array — stream element by element.
        # ijson yields decimal.Decimal for numbers; convert to float for
        # compatibility with downstream arithmetic in odds.py / predictions.py.
        with open(file_path, "rb") as f:
            for item in ijson.items(f, "item"):
                yield _decimals_to_float(item)
    elif first == b"{":
        # Single competition object (old format)
        with open(file_path, encoding="utf-8") as f:
            yield json.load(f)
    else:
        raise ValueError(f"Unrecognised JSON format in {file_path!r} (first byte: {first!r})")


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sportinerd — FanDuel ingestion v3")
    parser.add_argument(
        "--file", required=False, default=None,
        help="Path to FanDuel JSON file. Defaults to FANDUEL_SOURCE in .env",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse only — no DB writes")
    args = parser.parse_args()

    file_path = args.file or FANDUEL_SOURCE
    if not file_path:
        sys.exit(
            "[error] No source file specified.\n"
            "        Use --file <path>  or set FANDUEL_SOURCE in .env"
        )

    snapshot_at = datetime.now(tz=timezone.utc)
    start_ms    = time.time()
    print(f"[ingest] source={file_path}")
    print(f"[ingest] snapshot={snapshot_at.isoformat()}")
    print(f"[ingest] dry_run={args.dry_run}")

    if not args.dry_run:
        ensure_indexes()

    total_counts = defaultdict(int)
    total_errors = []
    comp_count   = 0

    for raw in iter_competitions(file_path):
        comp_name = raw.get("name", "Unknown")
        comp_id   = raw.get("competitionId", "?")
        print(f"\n── {comp_name}  (id={comp_id}) ──")

        parsed = parse(raw, snapshot_at)

        for e in parsed["errors"]:
            print(f"  [WARN] {e}")
            total_errors.append(e)

        n_fix     = len(parsed["fixtures"])
        n_players = sum(len(p[2]) for p in parsed["player_ops"])
        print(f"  fixtures={n_fix}  player_docs={n_players}  "
              f"teams={len(parsed['team_docs'])}  season={parsed['season_doc']['seasonYear']}")

        predictions = compute_all_predictions(parsed)
        for pred in predictions:
            m   = pred["match"]
            xgh = m.get("xGHome", {}).get("value", 0)
            xga = m.get("xGAway", {}).get("value", 0)
            print(f"  ⚽ {pred['homeTeam']} v {pred['awayTeam']}  "
                  f"xG={xgh:.2f}-{xga:.2f}  "
                  f"BTTS={m.get('btts',{}).get('value',0):.1f}%")

        counts = upsert(parsed, predictions, snapshot_at, dry_run=args.dry_run)
        for k, v in counts.items():
            total_counts[k] += v

        comp_count += 1

    # Purge stale data once after all competitions (not per-competition)
    if not args.dry_run:
        purged = purge_stale(snapshot_at)
        total_counts["snapshots_purged"] = purged
    else:
        total_counts["snapshots_purged"] = 0

    duration_ms = int((time.time() - start_ms) * 1000)

    print(f"\n{'─'*60}")
    print(f"[done] {comp_count} competitions  {duration_ms}ms")
    for k, v in total_counts.items():
        print(f"  {k:<32} {v}")

    if not args.dry_run:
        db = get_db()
        db[COL_INGESTION_LOG].insert_one({
            "source":           "fanduel",
            "filename":         file_path,
            "competitionCount": comp_count,
            "status":           "success" if not total_errors else "partial",
            "counts":           dict(total_counts),
            "errors":           total_errors,
            "durationMs":       duration_ms,
            "snapshotAt":       snapshot_at,
            "createdAt":        snapshot_at,
        })
        print("[ingest] Log written.")


if __name__ == "__main__":
    main()
