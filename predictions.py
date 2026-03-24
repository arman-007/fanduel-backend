# ─────────────────────────────────────────────────────────────────────────────
#  predictions.py  —  internal prediction engine
#
#  ALL predictions are computed AT INGEST TIME from already-normalised data.
#  Every prediction carries a 'source' and 'method' field:
#
#    source: "feed"    → value comes directly from FanDuel market data
#    source: "derived" → value is computed by our internal model
#
#  source: "feed" predictions are EXACT (subject to FanDuel overround removal).
#  source: "derived" predictions involve ASSUMPTIONS — documented per method.
#
#  ─── METHOD CATALOGUE ────────────────────────────────────────────────────────
#
#  cs_matrix
#    Input:  normalised Correct Score probabilities (sum ≈ 100%)
#    Output: cleanSheet, btts, xG, overUnder
#    Assumptions: none — pure weighted sums from market data
#    Accuracy: as good as the CS market is efficient
#
#  poisson_xg
#    Input:  xG (from cs_matrix), SOT_GOAL_CONVERSION constant
#    Output: GK saves 3+ probability
#    Formula:
#      expected_sot_faced = xG_against / SOT_GOAL_CONVERSION
#      expected_saves     = expected_sot_faced × (1 − SOT_GOAL_CONVERSION)
#                         = xG_against × ((1 / 0.35) − 1)
#                         = xG_against × 1.857
#      P(saves ≥ 3)       = 1 − Poisson_CDF(k=2, λ=expected_saves)
#    Assumptions:
#      • SOT_GOAL_CONVERSION = 0.35 (UEFA avg 33-37%, midpoint)
#      • Saves follow a Poisson distribution
#      • Home GK faces away xG; Away GK faces home xG
#    Confidence: MEDIUM — reasonable for planning, not for betting
#
#  independence_approximation
#    Input:  P(A anytime scorer), P(B anytime assist), xG_total
#    Output: P(A scores AND B assists on that goal)
#    Formula:
#      P(combo) ≈ P(A scores) × [P(B assists) / (xG_total × ASSIST_RATE)] × 100
#    Plain English:
#      "P(B assists) / (xG_total × assist_rate)" approximates the fraction
#      of goals that B assists, scaled to the expected number of assisted goals.
#      Multiplied by P(A scores) → probability that A scores a goal B assists.
#    Assumptions:
#      • ASSIST_RATE = 0.78 (78% of goals have credited assist, Opta/StatsBomb avg)
#      • Scorer and assister are INDEPENDENT events (they are NOT — teams/tactics
#        create correlation). This underestimates high-chemistry pairs.
#      • Only applies when GOALSCORER_ASSIST_DOUBLE is absent from FanDuel feed
#    Confidence: LOW — directional only, useful for ranking pairs not absolute values
# ─────────────────────────────────────────────────────────────────────────────

import math
from typing import Dict, List

from config import (
    SOT_GOAL_CONVERSION, ASSIST_RATE,
    COMBO_TOP_SCORERS, COMBO_TOP_ASSISTERS, COMBO_TOP_OUTPUT,
)

# Over/Under threshold labels (stored as string keys in MongoDB)
_OU_LABELS = {0.5: "over05", 1.5: "over15", 2.5: "over25", 3.5: "over35", 4.5: "over45"}


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _pred(value: float, source: str, method: str, assumptions: Dict = None) -> Dict:
    """Wrap a prediction value with provenance metadata (G5 compliance)."""
    out = {
        "value":       round(value, 4),
        "source":      source,
        "method":      method,
        "assumptions": assumptions or {},
    }
    return out


def _poisson_cdf(k: int, lam: float) -> float:
    """
    Cumulative Poisson probability P(X <= k).
    Manual implementation — avoids scipy dependency.
    """
    if lam <= 0:
        return 1.0
    total = 0.0
    log_lam = math.log(lam)
    log_factorial = 0.0
    for i in range(k + 1):
        if i > 0:
            log_factorial += math.log(i)
        log_pmf = i * log_lam - lam - log_factorial
        total += math.exp(log_pmf)
    return min(total, 1.0)


# ══════════════════════════════════════════════════════════════════════════════
#  MATCH PREDICTIONS  (from Correct Score matrix)
# ══════════════════════════════════════════════════════════════════════════════

def compute_match_predictions(cs_runners: List[Dict]) -> Dict:
    """
    Derive all match-level predictions from the normalised Correct Score matrix.

    Returns a dict with keys:
      homeCleanSheet, awayCleanSheet, btts,
      xGHome, xGAway,
      overUnder: { over05, over15, over25, over35, over45 }

    Probabilities are percentages (0-100).
    xG values are expected goal counts (e.g. 1.84), NOT percentages.
    """
    if not cs_runners:
        return {}

    home_cs = 0.0   # P(awayGoals == 0)
    away_cs = 0.0   # P(homeGoals == 0)
    btts    = 0.0   # P(homeGoals > 0 AND awayGoals > 0)
    xg_home = 0.0   # E[homeGoals]
    xg_away = 0.0   # E[awayGoals]
    over    = {0.5: 0.0, 1.5: 0.0, 2.5: 0.0, 3.5: 0.0, 4.5: 0.0}

    for r in cs_runners:
        hg = r.get("scoreHome", 0) or 0
        ag = r.get("scoreAway", 0) or 0
        p  = r.get("normalizedProbability", 0.0)   # probability in % (0-100)

        if ag == 0:
            home_cs += p
        if hg == 0:
            away_cs += p
        if hg > 0 and ag > 0:
            btts += p

        # xG: weighted average goals — divide p by 100 for proper expectation
        xg_home += (p / 100.0) * hg
        xg_away += (p / 100.0) * ag

        total = hg + ag
        for threshold in over:
            if total > threshold:
                over[threshold] += p

    method = "cs_matrix"
    _cs_assumptions = {
        "note": "Pure weighted sums from normalised Correct Score market. No external constants used.",
        "input": "normalised_correct_score_probabilities",
    }
    return {
        "homeCleanSheet": _pred(home_cs, "derived", method, _cs_assumptions),
        "awayCleanSheet": _pred(away_cs, "derived", method, _cs_assumptions),
        "btts":           _pred(btts,    "derived", method, _cs_assumptions),
        "xGHome":         {
            "value":       round(xg_home, 4),
            "source":      "derived",
            "method":      method,
            "unit":        "expected_goals",
            "assumptions": _cs_assumptions,
        },
        "xGAway":         {
            "value":       round(xg_away, 4),
            "source":      "derived",
            "method":      method,
            "unit":        "expected_goals",
            "assumptions": _cs_assumptions,
        },
        "overUnder":      {_OU_LABELS[t]: _pred(over[t], "derived", method, _cs_assumptions) for t in _OU_LABELS},
    }


# ══════════════════════════════════════════════════════════════════════════════
#  GK SAVES PREDICTIONS  (Poisson model from xG)
# ══════════════════════════════════════════════════════════════════════════════

def compute_gk_saves(
    home_team: str,
    away_team: str,
    xg_home: float,   # expected goals by home team -> away GK faces this
    xg_away: float,   # expected goals by away team -> home GK faces this
) -> List[Dict]:
    """
    Estimate P(GK makes 3+ saves) for each team's goalkeeper using Poisson model.

    Returns list of 2 dicts (home GK, away GK) each with:
      teamSide, teamName, xGAgainst, expectedSoT, expectedSaves, prob3Plus, source, method
    """
    results = []
    for side, team, xg_against in [
        ("home", home_team, xg_away),   # home GK faces away's xG
        ("away", away_team, xg_home),   # away GK faces home's xG
    ]:
        if xg_against <= 0:
            continue

        # SoT faced = goals expected / conversion rate
        # Saves     = SoT faced - goals conceded = xG * (1/conv - 1)
        #           = xG * 1.857
        expected_sot   = xg_against / SOT_GOAL_CONVERSION
        expected_saves = expected_sot * (1 - SOT_GOAL_CONVERSION)

        # P(saves >= 3) = 1 - P(saves <= 2)
        prob_3plus = (1.0 - _poisson_cdf(2, expected_saves)) * 100.0

        results.append({
            "teamSide":      side,
            "teamName":      team,
            "xGAgainst":     round(xg_against, 4),
            "expectedSoT":   round(expected_sot, 4),
            "expectedSaves": round(expected_saves, 4),
            "prob3Plus":     round(prob_3plus, 4),
            "source":        "derived",
            "method":        "poisson_xg",
            "assumptions": {
                "sot_goal_conversion": SOT_GOAL_CONVERSION,
                "note": "35% of SoT become goals (UEFA avg). Saves modelled as Poisson(lambda).",
            },
        })
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  G+A COMBO PREDICTIONS  (independence approximation)
#  Only used when GOALSCORER_ASSIST_DOUBLE market is ABSENT from feed
# ══════════════════════════════════════════════════════════════════════════════

def compute_derived_combos(
    players: List[Dict],
    xg_home: float,
    xg_away: float,
) -> List[Dict]:
    """
    Derive G+A combinations when the GOALSCORER_ASSIST_DOUBLE market
    is missing from the FanDuel feed.

    Formula:
      P(combo) = P(A scores) * [P(B assists) / (xG_total * ASSIST_RATE)]

    Returns top COMBO_TOP_OUTPUT pairs sorted by derived probability desc.
    Each pair carries source="derived" and full assumption disclosure.
    """
    xg_total = xg_home + xg_away
    if xg_total <= 0:
        return []

    scorers   = []
    assisters = []
    for p in players:
        m = p.get("markets", {})
        if "anytimeGoalscorer" in m:
            scorers.append({
                "id":   p["sportinerdPlayerId"],
                "name": p["playerName"],
                "prob": m["anytimeGoalscorer"],
            })
        if "anytimeAssist" in m:
            assisters.append({
                "id":   p["sportinerdPlayerId"],
                "name": p["playerName"],
                "prob": m["anytimeAssist"],
            })

    scorers   = sorted(scorers,   key=lambda x: x["prob"], reverse=True)[:COMBO_TOP_SCORERS]
    assisters = sorted(assisters, key=lambda x: x["prob"], reverse=True)[:COMBO_TOP_ASSISTERS]

    combos = []
    denominator = xg_total * ASSIST_RATE   # expected assisted goals in match

    for s in scorers:
        for a in assisters:
            if s["id"] == a["id"]:
                continue   # player cannot assist their own goal
            p_score  = s["prob"] / 100.0
            p_assist = a["prob"] / 100.0
            derived  = (p_score * (p_assist / denominator)) * 100.0
            combos.append({
                "scorerId":     s["id"],
                "scorerName":   s["name"],
                "assisterId":   a["id"],
                "assisterName": a["name"],
                "scorerProb":   round(s["prob"], 4),
                "assisterProb": round(a["prob"], 4),
                "probability":  round(derived, 4),
                "source":       "derived",
                "method":       "independence_approximation",
                "assumptions": {
                    "assist_rate": ASSIST_RATE,
                    "xg_total":    round(xg_total, 4),
                    "note": (
                        "Scorer and assister treated as independent. "
                        "Chemistry/tactical correlation not modelled. "
                        "Confidence: LOW — use for ranking only."
                    ),
                },
            })

    combos.sort(key=lambda x: x["probability"], reverse=True)
    return combos[:COMBO_TOP_OUTPUT]


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def build_predictions(
    fixture: Dict,
    players: List[Dict],
    has_combo_feed: bool,
) -> Dict:
    """
    Build the full predictions document for one fixture.

    Args:
        fixture:        parsed fixture doc (with matchOdds.correctScore)
        players:        list of player dicts (with sportinerdPlayerId + markets)
        has_combo_feed: True if GOALSCORER_ASSIST_DOUBLE exists in feed for this fixture

    Returns a predictions doc ready for MongoDB upsert.
    """
    cs_runners  = fixture.get("matchOdds", {}).get("correctScore", [])
    match_preds = compute_match_predictions(cs_runners)

    xg_home = match_preds.get("xGHome", {}).get("value", 0.0)
    xg_away = match_preds.get("xGAway", {}).get("value", 0.0)

    gk_saves = compute_gk_saves(
        home_team=fixture.get("homeTeam", ""),
        away_team=fixture.get("awayTeam", ""),
        xg_home=xg_home,
        xg_away=xg_away,
    )

    if has_combo_feed:
        derived_combos = []
        combo_note     = "feed_data_available"
    else:
        derived_combos = compute_derived_combos(players, xg_home, xg_away)
        combo_note     = "derived_independence_approximation"

    return {
        "fixtureId":           fixture.get("fixtureId"),
        "sportinerdFixtureId": fixture.get("sportinerdFixtureId"),
        "competitionId":       fixture.get("competitionId"),
        "homeTeam":            fixture.get("homeTeam"),
        "awayTeam":            fixture.get("awayTeam"),
        "match":               match_preds,
        "gkSaves":             gk_saves,
        "combos": {
            "source": "feed" if has_combo_feed else "derived",
            "note":   combo_note,
            "pairs":  derived_combos,
        },
        "snapshotAt": fixture.get("snapshotAt"),
        "updatedAt":  fixture.get("snapshotAt"),
    }
