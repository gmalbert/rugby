"""
World Rugby Pulse Live API — used for Six Nations fixtures and results.
"""

import requests
import pandas as pd
import logging

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ScrumBet/1.0)"}
_BASE = "https://api.wr-rims-prod.pulselive.com/rugby/v3"

# World Rugby competition IDs
_COMPETITION_IDS: dict[str, str] = {
    "six_nations":   "180659",
    "champions_cup": "271937",
}


def _get(path: str, params: dict | None = None) -> dict | None:
    try:
        r = requests.get(f"{_BASE}{path}", params=params,
                         headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("World Rugby %s → %s", path, e)
        return None


def fetch_fixtures(league_id: str) -> pd.DataFrame:
    comp_id = _COMPETITION_IDS.get(league_id)
    if not comp_id:
        return pd.DataFrame()

    data = _get("/match", params={
        "matchStatus": "C,L,U",
        "sort":        "asc",
        "pageSize":    100,
        "competition": comp_id,
    })
    if not data:
        return pd.DataFrame()

    records = []
    for match in data.get("content", []):
        teams = match.get("teams", [])
        if len(teams) < 2:
            continue

        home = next((t for t in teams if t.get("home")), teams[0])
        away = next((t for t in teams if not t.get("home")), teams[1])

        status_id = match.get("status", "U")
        status    = "final" if status_id == "C" else ("live" if status_id == "L" else "scheduled")

        millis = match.get("time", {}).get("millis")
        kickoff = pd.Timestamp(millis, unit="ms", tz="UTC").isoformat() if millis else ""

        h_slug = home.get("team", {}).get("slug") or str(home.get("team", {}).get("id", ""))
        a_slug = away.get("team", {}).get("slug") or str(away.get("team", {}).get("id", ""))

        records.append({
            "id":           str(match.get("matchId", "")),
            "league_id":    league_id,
            "home_team_id": f"{league_id}-{h_slug}",
            "away_team_id": f"{league_id}-{a_slug}",
            "kickoff_utc":  kickoff,
            "home_score":   int(home.get("score", 0) or 0),
            "away_score":   int(away.get("score", 0) or 0),
            "home_tries":   0,
            "away_tries":   0,
            "status":       status,
            "venue":        (match.get("venue") or {}).get("name", ""),
            "round":        int((match.get("round") or {}).get("roundNumber") or 0),
        })

    return pd.DataFrame(records)
