"""
Client for ParlayAPI (https://parlay-api.com).

Real-time odds aggregation from 15 sources, updated every 60-90 seconds.
66 sports: MLB, NFL, NBA, NHL, MMA/UFC, 51 soccer leagues, NRL rugby league.
Bookmakers: DraftKings, FanDuel, Caesars, Bovada, Pinnacle, Fliff.
DFS: PrizePicks, Underdog, Betr, Pick6, Sleeper.
Exchanges: Novig, ProphetX.

Authentication: X-API-Key header (preferred) or ?apiKey= query param.
Free tier: 1,000 credits/month.

IMPORTANT: A browser-like User-Agent header is required. Cloudflare will return
403 Error 1010 for the default Python urllib user-agent.

Usage:
    from utils.parlay_api import get_events, get_odds, get_usage
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE = "https://parlay-api.com"

# Cloudflare blocks the default Python UA with 403 Error 1010.
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ── Core HTTP helper ──────────────────────────────────────────────────────

def _api_get(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    auth: bool = True,
) -> tuple[Any, dict, int]:
    """
    GET {BASE}/{path} with optional query params.
    Returns (body, response_headers, status_code).
    Raises urllib.error.HTTPError on non-2xx.
    """
    url = f"{BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": _UA,
    }
    if auth:
        api_key = os.environ.get("PARLAY_API_KEY", "")
        if api_key:
            headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()), dict(resp.headers), resp.status
    except urllib.error.HTTPError as exc:
        raise


# ── Free / no-credit endpoints ────────────────────────────────────────────

def get_sports(include_inactive: bool = False) -> list[dict]:
    """
    List all 66 supported sports. FREE – no credits charged.

    Returns list of {key, group, title, description, active, has_outrights}.
    Pass include_inactive=True to include off-season sports.
    """
    params: dict[str, Any] = {}
    if include_inactive:
        params["all"] = "true"
    body, _, _ = _api_get("/v1/sports", params or None)
    return body if isinstance(body, list) else []


def get_events(
    sport_key: str,
    *,
    event_ids: str | None = None,
    commence_time_from: str | None = None,
    commence_time_to: str | None = None,
    date_format: str = "iso",
) -> list[dict]:
    """
    List upcoming events for a sport. FREE – no credits charged.

    Returns list of {id, canonical_event_id, sport_key, sport_title,
    commence_time, home_team, away_team}.

    commence_time_from/to: ISO 8601 strings, e.g. "2026-05-01T00:00:00Z"
    """
    params: dict[str, Any] = {"dateFormat": date_format}
    if event_ids:
        params["eventIds"] = event_ids
    if commence_time_from:
        params["commenceTimeFrom"] = commence_time_from
    if commence_time_to:
        params["commenceTimeTo"] = commence_time_to
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/events", params)
    return body if isinstance(body, list) else []


def list_prop_markets(sport_key: str) -> list[str]:
    """List available prop market keys for a sport. FREE – no credits charged."""
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/props/markets")
    return body if isinstance(body, list) else []


def get_usage() -> dict:
    """
    Return credit usage for the current billing period. FREE.

    Returns {credits_used, credits_remaining, credits_total, tier,
    period_start, period_end}.
    """
    body, _, _ = _api_get("/v1/usage")
    return body if isinstance(body, dict) else {}


def get_public_stats() -> dict:
    """Return public data availability stats. FREE – no auth needed."""
    body, _, _ = _api_get("/v1/stats", auth=False)
    return body if isinstance(body, dict) else {}


def get_live_sports() -> list[dict]:
    """
    Return sports with active live events and event counts. FREE – no auth.

    Returns list of {key, title, event_count}.
    """
    body, _, _ = _api_get("/live/api/sports", auth=False)
    return body if isinstance(body, list) else []


# ── Paid endpoints ────────────────────────────────────────────────────────

def get_odds(
    sport_key: str,
    *,
    regions: str = "us",
    markets: str = "h2h",
    odds_format: str = "american",
    bookmakers: str | None = None,
    event_ids: str | None = None,
    commence_time_from: str | None = None,
    commence_time_to: str | None = None,
    date_format: str = "iso",
) -> list[dict]:
    """
    Get odds for upcoming and live events.
    Credits: markets_count × regions_count  (same formula as the-odds-api).

    regions:    comma-separated from us, us2, uk, eu, au
                Use eu for Pinnacle and European bookmakers.
    markets:    comma-separated from h2h, spreads, totals
    bookmakers: comma-separated key list (overrides regions)

    Returns list of {id, sport_key, sport_title, commence_time,
    home_team, away_team, bookmakers, canonical_event_id}.
    Each bookmaker: {key, title, last_update, markets: [{key, last_update,
    outcomes: [{name, price}]}]}.
    """
    params: dict[str, Any] = {
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
        "dateFormat": date_format,
    }
    if bookmakers:
        params["bookmakers"] = bookmakers
    if event_ids:
        params["eventIds"] = event_ids
    if commence_time_from:
        params["commenceTimeFrom"] = commence_time_from
    if commence_time_to:
        params["commenceTimeTo"] = commence_time_to
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/odds", params)
    return body if isinstance(body, list) else []


def get_event_odds(
    sport_key: str,
    event_id: str,
    *,
    regions: str = "us",
    markets: str = "h2h",
    odds_format: str = "american",
) -> dict:
    """
    Get odds for a single event.
    Credits: markets_count × regions_count.
    """
    params: dict[str, Any] = {
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    }
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/events/{event_id}/odds", params)
    return body if isinstance(body, dict) else {}


def get_scores(sport_key: str, *, days_from: int = 1) -> list[dict]:
    """
    Get live scores and recent results. 1–2 credits.

    days_from: 1–3 days of completed results to include.
    Covers NHL, NBA, MLB, NFL, MMA/UFC, and major soccer leagues via ESPN.
    NOTE: Rugby (rugbyleague_nrl) returned empty in testing (Apr 2026).
    """
    params: dict[str, Any] = {"daysFrom": days_from}
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/scores", params)
    return body if isinstance(body, list) else []


def get_props(
    sport_key: str,
    *,
    markets: str | None = None,
    bookmakers: str | None = None,
    player: str | None = None,
    event_id: str | None = None,
    odds_format: str = "american",
    grouped: bool = True,
    limit: int = 5000,
) -> list[dict]:
    """
    Get player prop odds from 10+ sources. 3 credits.

    markets: comma-separated prop market keys, e.g. "player_points,player_rebounds"
    grouped=True returns one entry per prop with a books[] array (recommended).
    """
    params: dict[str, Any] = {
        "oddsFormat": odds_format,
        "grouped": "true" if grouped else "false",
        "limit": limit,
    }
    if markets:
        params["markets"] = markets
    if bookmakers:
        params["bookmakers"] = bookmakers
    if player:
        params["player"] = player
    if event_id:
        params["eventId"] = event_id
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/props", params)
    return body if isinstance(body, list) else []


def get_line_movement(
    sport_key: str,
    event_id: str,
    *,
    market: str | None = None,
    player: str | None = None,
    source: str | None = None,
    hours: int = 24,
) -> list[dict]:
    """
    Track how odds move over time for an event. 2 credits.

    Returns time-series of odds snapshots for steam detection / CLV analysis.
    hours: lookback window (max 168).
    """
    params: dict[str, Any] = {"eventId": event_id, "hours": hours}
    if market:
        params["market"] = market
    if player:
        params["player"] = player
    if source:
        params["source"] = source
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/line-movement", params)
    return body if isinstance(body, list) else []


def get_futures(sport_key: str, *, bookmakers: str | None = None) -> list[dict]:
    """Get futures/outrights odds (championship winners, MVP, etc). 5 credits."""
    params: dict[str, Any] = {}
    if bookmakers:
        params["bookmakers"] = bookmakers
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/futures", params or None)
    return body if isinstance(body, list) else []


def get_closing_lines(
    sport_key: str,
    *,
    bookmakers: str = "pinnacle",
    days_from: int = 3,
    odds_format: str = "american",
) -> list[dict]:
    """
    Get closing lines (last odds before match start). 5 credits. EXCLUSIVE.

    Essential for CLV (closing line value) analysis.
    Supports all 66 sports; Pinnacle closing lines available for all 51 soccer leagues.
    days_from: max 30.
    """
    params: dict[str, Any] = {
        "bookmakers": bookmakers,
        "daysFrom": days_from,
        "oddsFormat": odds_format,
    }
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/closing-lines", params)
    return body if isinstance(body, list) else []


def find_ev(
    sport_key: str,
    *,
    sharp_book: str = "pinnacle",
    min_edge: float = 2.0,
) -> list[dict]:
    """
    Find +EV bets by comparing sharp vs soft book lines. 10 credits. EXCLUSIVE.

    min_edge: minimum edge % to include (e.g. 2.0 = 2%).
    """
    params: dict[str, Any] = {"sharpBook": sharp_book, "minEdge": min_edge}
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/ev", params)
    return body if isinstance(body, list) else []


def find_arbitrage(sport_key: str, *, min_profit: float = 0.0) -> list[dict]:
    """
    Find arbitrage opportunities across bookmakers. 10 credits. EXCLUSIVE.

    min_profit: minimum profit % to include (e.g. 1.5 = 1.5%).
    """
    params: dict[str, Any] = {"minProfit": min_profit}
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/arbitrage", params)
    return body if isinstance(body, list) else []


def get_consensus(sport_key: str) -> list[dict]:
    """
    Get average, best, and worst odds + hold% across all bookmakers. 3 credits.
    """
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/consensus")
    return body if isinstance(body, list) else []


def compare_odds(
    sport_key: str, *, markets: str = "h2h", odds_format: str = "american"
) -> list[dict]:
    """
    Compare odds across all bookmakers side-by-side. 5 credits. EXCLUSIVE.

    Returns each event with per-bookmaker odds and the best available line.
    """
    params: dict[str, Any] = {"markets": markets, "oddsFormat": odds_format}
    body, _, _ = _api_get(f"/v1/sports/{sport_key}/compare", params)
    return body if isinstance(body, list) else []


def get_historical_odds(
    sport_key: str,
    date: str,
    *,
    regions: str = "eu",
    markets: str = "h2h",
    odds_format: str = "american",
) -> list[dict]:
    """
    Get historical odds at a point in time. 10 × markets × regions credits.

    date: ISO 8601 timestamp, e.g. "2026-01-15T12:00:00Z"
    Archive covers 1M+ records from 2005-present.
    """
    params: dict[str, Any] = {
        "date": date,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    }
    body, _, _ = _api_get(f"/v1/historical/sports/{sport_key}/odds", params)
    return body if isinstance(body, list) else []


def get_historical_closing_odds(
    sport_key: str,
    *,
    bookmakers: str = "pinnacle",
    season: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    odds_format: str = "american",
) -> list[dict]:
    """
    Get historical closing odds from the archive. 10 credits.

    833,000+ records covering 19 soccer leagues from 2005-present.
    Includes match results for backtesting.
    season: e.g. "2023-24"
    date_from/to: "YYYY-MM-DD"
    """
    params: dict[str, Any] = {
        "bookmakers": bookmakers,
        "oddsFormat": odds_format,
    }
    if season:
        params["season"] = season
    if date_from:
        params["dateFrom"] = date_from
    if date_to:
        params["dateTo"] = date_to
    body, _, _ = _api_get(
        f"/v1/historical/sports/{sport_key}/closing-odds", params
    )
    return body if isinstance(body, list) else []


# ── Odds conversion helpers ───────────────────────────────────────────────

def american_to_implied(odds: int | float) -> float:
    """American money-line odds → implied probability [0, 1]."""
    o = float(odds)
    if o > 0:
        return 100.0 / (o + 100.0)
    return abs(o) / (abs(o) + 100.0)


def implied_to_american(prob: float) -> int:
    """Implied probability [0, 1] → American money-line odds (integer)."""
    if prob >= 0.5:
        return round(-prob / (1.0 - prob) * 100)
    return round((1.0 - prob) / prob * 100)


def format_american(odds: int | float) -> str:
    """Format American odds as '+150' or '-120'."""
    o = int(round(float(odds)))
    return f"+{o}" if o >= 0 else str(o)
