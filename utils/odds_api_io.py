"""
Client for odds-api.io (https://docs.odds-api.io/).

Covers 34 sports, 250+ bookmakers, real-time data.
Free plan: 100 req/hr, 2 pre-selected bookmakers (DraftKings + BetMGM BR).

Usage:
    from utils.odds_api_io import get_events, get_odds, decimal_to_american
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE = "https://api.odds-api.io/v3"


# ── Core HTTP helper ──────────────────────────────────────────────────────

def _api_get(path: str, params: dict[str, Any] | None = None) -> tuple[Any, dict]:
    """
    GET {BASE}/{path} with query params.
    Returns (body, response_headers).
    Raises urllib.error.HTTPError on non-2xx.
    """
    api_key = os.environ.get("ODDS_API_IO_KEY", "")
    all_params: dict[str, Any] = {"apiKey": api_key}
    if params:
        all_params.update(params)
    qs = urllib.parse.urlencode(all_params)
    req = urllib.request.Request(
        f"{BASE}/{path}?{qs}", headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read()), dict(resp.headers)


# ── Public API functions ──────────────────────────────────────────────────

def get_sports() -> list[dict]:
    """Return all sports (no auth required)."""
    req = urllib.request.Request(f"{BASE}/sports", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get_leagues(sport: str, include_empty: bool = False) -> list[dict]:
    """
    Return leagues for a sport.
    Set include_empty=True to discover all slugs including off-season.
    """
    params: dict[str, Any] = {"sport": sport}
    if include_empty:
        params["all"] = "true"
    body, _ = _api_get("leagues", params)
    return body if isinstance(body, list) else []


def get_events(
    sport: str,
    *,
    league: str | None = None,
    status: str = "pending,live",
    from_dt: str | None = None,
    to_dt: str | None = None,
    limit: int = 100,
    skip: int = 0,
) -> list[dict]:
    """
    Return events for a sport with optional filters.

    status: comma-separated from pending | live | settled
    from_dt / to_dt: RFC3339 strings, e.g. "2026-05-01T00:00:00Z"
    """
    params: dict[str, Any] = {
        "sport": sport,
        "status": status,
        "limit": limit,
        "skip": skip,
    }
    if league:
        params["league"] = league
    if from_dt:
        params["from"] = from_dt
    if to_dt:
        params["to"] = to_dt
    body, _ = _api_get("events", params)
    return body if isinstance(body, list) else []


def get_odds(event_id: int | str, bookmakers: list[str]) -> dict:
    """
    Return odds for a single event from the specified bookmakers.

    bookmakers must be within your plan's allowed set.
    Names with spaces (e.g. "BetMGM BR") are URL-encoded automatically.
    """
    params: dict[str, Any] = {
        "eventId": event_id,
        "bookmakers": ",".join(bookmakers),
    }
    body, _ = _api_get("odds", params)
    return body if isinstance(body, dict) else {}


def get_selected_bookmakers() -> list[str]:
    """Return the bookmakers allowed on the current plan."""
    body, _ = _api_get("bookmakers/selected")
    return body.get("bookmakers", []) if isinstance(body, dict) else []


def get_rate_limit() -> dict:
    """Return current rate-limit info (costs 1 request)."""
    _, hdrs = _api_get("bookmakers/selected")
    return {
        "limit":     int(hdrs.get("x-ratelimit-limit", 0) or 0),
        "remaining": int(hdrs.get("x-ratelimit-remaining", 0) or 0),
        "reset":     hdrs.get("x-ratelimit-reset", ""),
    }


# ── Odds conversion helpers ───────────────────────────────────────────────

def decimal_to_implied(decimal_odds: float) -> float:
    """Decimal odds (e.g. 1.45) → implied probability [0, 1]."""
    return 1.0 / float(decimal_odds)


def decimal_to_american(decimal_odds: float) -> int:
    """Decimal odds → American money-line odds (integer)."""
    d = float(decimal_odds)
    if d >= 2.0:
        return round((d - 1) * 100)
    return round(-100 / (d - 1))


def extract_market(markets: list[dict], name: str) -> list[dict]:
    """Extract the odds list for a named market from a bookmaker's market list."""
    for m in markets:
        if m.get("name") == name:
            return m.get("odds", [])
    return []


def main_spread_line(spread_odds: list[dict]) -> dict | None:
    """
    Return the spread entry whose handicap is closest to 0 (the main line).
    BetMGM BR returns every available handicap; this picks the principal one.
    """
    if not spread_odds:
        return None
    return min(spread_odds, key=lambda o: abs(float(o.get("hdp", 999))))


def main_totals_line(totals_odds: list[dict]) -> dict | None:
    """Return the primary game-total entry (first entry = main line)."""
    return totals_odds[0] if totals_odds else None


# ── Team-name normalisation for fuzzy event matching ─────────────────────

_STRIP_RE = re.compile(
    r"\b(rugby|union|league|football|fc|rc|rl|club|sport|sports|"
    r"county|city|united|town|athletic|athletico|nrl|afl)\b",
    re.IGNORECASE,
)


def normalize_team(name: str) -> str:
    """Lowercase, strip sport-type words, collapse whitespace."""
    name = name.lower()
    name = _STRIP_RE.sub("", name)
    name = re.sub(r"[^a-z0-9 ]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def names_match(a: str, b: str) -> bool:
    """
    True if two team names are a plausible match after normalisation.
    Uses prefix-match and shared-significant-word strategies.
    """
    na, nb = normalize_team(a), normalize_team(b)
    if na == nb:
        return True
    if na.startswith(nb) or nb.startswith(na):
        return True
    wa = {w for w in na.split() if len(w) >= 4}
    wb = {w for w in nb.split() if len(w) >= 4}
    return bool(wa & wb)
