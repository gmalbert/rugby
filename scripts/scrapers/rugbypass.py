"""
RugbyPass JSON scraper.

RugbyPass inlines structured JSON in a __NEXT_DATA__ <script> tag on most
pages — no JS rendering required.
"""

import requests
import json
import logging
import time
from bs4 import BeautifulSoup
import pandas as pd

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ScrumBet/1.0)"}
_RATE_LIMIT = 3  # seconds between requests

_LEAGUE_SLUGS: dict[str, str] = {
    "premiership":   "gallagher-premiership",
    "top14":         "top-14",
    "urc":           "united-rugby-championship",
    "champions_cup": "heineken-champions-cup",
    "super_rugby":   "super-rugby-pacific",
    "six_nations":   "six-nations",
}


def _next_data(url: str) -> dict | None:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        soup   = BeautifulSoup(resp.text, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script:
            logger.warning("No __NEXT_DATA__ at %s", url)
            return None
        return json.loads(script.string)
    except Exception as e:
        logger.warning("RugbyPass error %s: %s", url, e)
        return None


def fetch_standings(league_id: str) -> pd.DataFrame:
    slug = _LEAGUE_SLUGS.get(league_id)
    if not slug:
        return pd.DataFrame()

    data = _next_data(f"https://www.rugbypass.com/{slug}/standings/")
    if not data:
        return pd.DataFrame()

    try:
        pp = data.get("props", {}).get("pageProps", {})
        raw = pp.get("standings") or pp.get("data", {}).get("standings") or []
    except (KeyError, TypeError):
        return pd.DataFrame()

    records = []
    for e in raw:
        slug_val = e.get("teamSlug") or e.get("teamId") or ""
        records.append({
            "team_id":        f"{league_id}-{slug_val}",
            "league_id":      league_id,
            "season":         int(e.get("season", 0) or 0),
            "played":         int(e.get("played", 0) or 0),
            "won":            int(e.get("won", 0) or 0),
            "lost":           int(e.get("lost", 0) or 0),
            "drawn":          int(e.get("drawn", 0) or 0),
            "points_for":     int(e.get("pointsFor", 0) or 0),
            "points_against": int(e.get("pointsAgainst", 0) or 0),
            "tries_for":      int(e.get("triesFor", 0) or 0),
            "tries_against":  int(e.get("triesAgainst", 0) or 0),
            "bonus_points":   int(e.get("bonusPoints", 0) or 0),
            "league_points":  int(e.get("points", 0) or 0),
        })
    time.sleep(_RATE_LIMIT)
    return pd.DataFrame(records)


def fetch_fixtures(league_id: str) -> pd.DataFrame:
    slug = _LEAGUE_SLUGS.get(league_id)
    if not slug:
        return pd.DataFrame()

    data = _next_data(f"https://www.rugbypass.com/{slug}/fixtures-results/")
    if not data:
        return pd.DataFrame()

    try:
        pp  = data.get("props", {}).get("pageProps", {})
        raw = pp.get("fixtures") or pp.get("data", {}).get("fixtures") or []
    except (KeyError, TypeError):
        return pd.DataFrame()

    records = []
    for f in raw:
        h_slug = f.get("homeTeamSlug") or f.get("homeTeamId") or ""
        a_slug = f.get("awayTeamSlug") or f.get("awayTeamId") or ""
        status = (f.get("status", "") or "").lower()
        if "final" in status or "result" in status:
            status = "final"
        elif "live" in status:
            status = "live"
        else:
            status = "scheduled"

        records.append({
            "id":           str(f.get("id", "")),
            "league_id":    league_id,
            "home_team_id": f"{league_id}-{h_slug}",
            "away_team_id": f"{league_id}-{a_slug}",
            "kickoff_utc":  f.get("kickoffDateUtc") or f.get("datetime", ""),
            "home_score":   int(f.get("homeScore", 0) or 0),
            "away_score":   int(f.get("awayScore", 0) or 0),
            "home_tries":   int(f.get("homeTries", 0) or 0),
            "away_tries":   int(f.get("awayTries", 0) or 0),
            "status":       status,
            "venue":        f.get("venue", ""),
            "round":        int(f.get("round", 0) or 0),
        })

    time.sleep(_RATE_LIMIT)
    return pd.DataFrame(records)
