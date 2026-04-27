"""
SofaScore reverse-engineered API — live scores and match stats.
"""

import requests
import pandas as pd
import logging
from datetime import date, timedelta
from utils.config import SOFASCORE_BASE

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent":  "Mozilla/5.0 (compatible; ScrumBet/1.0)",
    "Accept":      "application/json",
    "Referer":     "https://www.sofascore.com/",
}


def _get(path: str) -> dict | None:
    try:
        r = requests.get(f"{SOFASCORE_BASE}{path}", headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("SofaScore %s → %s", path, e)
        return None


def fetch_scheduled(days_ahead: int = 1) -> pd.DataFrame:
    """
    Fetch fixtures for today + `days_ahead` days.
    Returns a DataFrame with live/scheduled match info.
    """
    all_events: list[dict] = []
    for offset in range(days_ahead + 1):
        d    = (date.today() + timedelta(days=offset)).isoformat()
        data = _get(f"/sport/rugby-union/scheduled-events/{d}")
        if data:
            all_events.extend(data.get("events", []))

    records = []
    for event in all_events:
        status_type = event.get("status", {}).get("type", "")
        if status_type == "inprogress":
            status = "live"
        elif status_type == "finished":
            status = "final"
        else:
            status = "scheduled"

        records.append({
            "id":         str(event.get("id")),
            "home_team":  event.get("homeTeam", {}).get("name", ""),
            "away_team":  event.get("awayTeam", {}).get("name", ""),
            "home_score": event.get("homeScore", {}).get("current", 0),
            "away_score": event.get("awayScore", {}).get("current", 0),
            "minute":     event.get("status", {}).get("description", ""),
            "status":     status,
            "tournament": event.get("tournament", {}).get("name", ""),
        })

    return pd.DataFrame(records)


def fetch_live_scores() -> pd.DataFrame:
    data = _get("/sport/rugby-union/scheduled-events/live")
    if not data:
        return pd.DataFrame(columns=["id", "home_team", "away_team",
                                     "home_score", "away_score", "minute",
                                     "status", "tournament"])
    records = []
    for event in data.get("events", []):
        records.append({
            "id":         str(event.get("id")),
            "home_team":  event.get("homeTeam", {}).get("name", ""),
            "away_team":  event.get("awayTeam", {}).get("name", ""),
            "home_score": event.get("homeScore", {}).get("current", 0),
            "away_score": event.get("awayScore", {}).get("current", 0),
            "minute":     event.get("status", {}).get("description", ""),
            "status":     "live",
            "tournament": event.get("tournament", {}).get("name", ""),
        })
    return pd.DataFrame(records)


def fetch_match_statistics(event_id: str) -> dict:
    return _get(f"/event/{event_id}/statistics") or {}


def fetch_lineups(event_id: str) -> dict:
    return _get(f"/event/{event_id}/lineups") or {}
