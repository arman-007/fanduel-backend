# ─────────────────────────────────────────────
#  odds.py  —  odds conversion helpers
# ─────────────────────────────────────────────
from typing import List, Dict, Any


def decimal_to_raw(decimal_odds: float) -> float:
    """
    Convert decimal odds to raw (implied) probability %.
    raw = (1 / decimal_odds) * 100
    """
    if decimal_odds <= 0:
        return 0.0
    return round((1 / decimal_odds) * 100, 6)


def normalise(runners: List[Dict]) -> List[Dict]:
    """
    Remove bookmaker overround from a mutually-exclusive market.
    Each runner must have a 'rawProbability' field already set.
    Adds 'normalizedProbability' to each runner in-place and returns the list.
    """
    total = sum(r["rawProbability"] for r in runners)
    if total == 0:
        for r in runners:
            r["normalizedProbability"] = 0.0
    else:
        for r in runners:
            r["normalizedProbability"] = round((r["rawProbability"] / total) * 100, 4)
    return runners


def extract_decimal(runner: Dict) -> float:
    """
    Safely extract decimalOdds from a FanDuel runner dict.
    Path: winRunnerOdds.trueOdds.decimalOdds.decimalOdds
    """
    try:
        return runner["winRunnerOdds"]["trueOdds"]["decimalOdds"]["decimalOdds"]
    except (KeyError, TypeError):
        return 0.0


def extract_american(runner: Dict) -> int:
    """
    Safely extract americanOdds from a FanDuel runner dict.
    """
    try:
        return runner["winRunnerOdds"]["americanDisplayOdds"]["americanOddsInt"]
    except (KeyError, TypeError):
        return 0


def build_runner_base(runner: Dict) -> Dict:
    """
    Build the base dict shared by all runner types:
    selectionId, name, logo, americanOdds, decimalOdds, rawProbability
    """
    decimal = extract_decimal(runner)
    return {
        "selectionId":   runner.get("selectionId"),
        "name":          runner.get("runnerName", ""),
        "logo":          runner.get("logo"),
        "americanOdds":  extract_american(runner),
        "decimalOdds":   decimal,
        "rawProbability": decimal_to_raw(decimal),
    }
