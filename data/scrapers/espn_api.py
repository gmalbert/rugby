"""ESPN API scraper — matches, teams, standings.

Base URL:  https://site.api.espn.com/apis/site/v2/sports/rugby/{espn_league_id}/...

Working endpoints (confirmed):
  /{id}/teams          — team list for a league
  /{id}/scoreboard     — events with scores/status/competitors
  /{id}/summary?event= — event detail incl. embedded standings + boxscore

Broken endpoints (do not use):
  /{id}/standings      — returns {"fullViewLink": ...} only
  /event/{id}/summary  — 400 error; must use /{league_id}/summary?event=
  /league/{id}/...     — 404 (old v2 path)
  Rugby boxscore player stats — always returns 0 rows; player stats skipped.

Circuit-breaker: after 3 consecutive failures on a URL prefix, that endpoint
is skipped for the remainder of the run to avoid hammering dead URLs.
"""

import requests
import pandas as pd
import logging
from datetime import datetime
from utils.config import ESPN_BASE, ESPN_LEAGUE_IDS

logger = logging.getLogger(__name__)

# ── Circuit-breaker ────────────────────────────────────────────────────────

_cb_failures: dict[str, int] = {}
_CB_THRESHOLD = 3


def _cb_key(url: str) -> str:
    # key = scheme + host + first 5 path segments (enough to identify endpoint type)
    parts = url.split("/")
    return "/".join(parts[:8])


def _cb_open(url: str) -> bool:
    if _cb_failures.get(_cb_key(url), 0) >= _CB_THRESHOLD:
        logger.debug("Circuit-breaker OPEN — skipping %s", _cb_key(url))
        return True
    return False


def _cb_ok(url: str) -> None:
    _cb_failures[_cb_key(url)] = 0


def _cb_fail(url: str) -> None:
    key = _cb_key(url)
    _cb_failures[key] = _cb_failures.get(key, 0) + 1
    if _cb_failures[key] == _CB_THRESHOLD:
        logger.warning(
            "Circuit-breaker OPEN for '%s' after %d failures — will skip for this run",
            key, _CB_THRESHOLD,
        )

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ScrumBet/1.0)",
    "Accept": "application/json",
}


def _get(url: str, params: dict | None = None) -> dict | None:
    """GET JSON with circuit-breaker protection."""
    if _cb_open(url):
        return None
    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=15)
        if r.status_code in (400, 404):
            logger.warning("ESPN %d — dead endpoint: %s  params=%s", r.status_code, url, params)
            _cb_fail(url)
            return None
        r.raise_for_status()
        _cb_ok(url)
        return r.json()
    except requests.HTTPError as e:
        logger.warning("ESPN HTTP error %s → %s", url, e)
        _cb_fail(url)
        return None
    except Exception as e:
        logger.warning("ESPN request failed %s → %s", url, e)
        _cb_fail(url)
        return None


# ── Teams ──────────────────────────────────────────────────────────────────

def fetch_teams(league_id: str) -> pd.DataFrame:
    """Fetch all teams for a league using ESPN numeric team IDs."""
    espn_id = ESPN_LEAGUE_IDS.get(league_id)
    if not espn_id:
        return pd.DataFrame()

    data = _get(f"{ESPN_BASE}/{espn_id}/teams")
    if not data:
        return pd.DataFrame()

    teams_raw = (
        data.get("sports", [{}])[0]
            .get("leagues", [{}])[0]
            .get("teams", [])
    )
    if not teams_raw:
        logger.warning("ESPN teams: no teams in response for %s", league_id)
        return pd.DataFrame()

    records = []
    for item in teams_raw:
        t = item.get("team", item)
        espn_tid = str(t.get("id", ""))
        if not espn_tid:
            continue
        logos    = t.get("logos") or []
        logo_url = logos[0].get("href", "") if logos else ""
        records.append({
            "id":         f"{league_id}-{espn_tid}",
            "espn_id":    espn_tid,
            "league_id":  league_id,
            "name":       t.get("displayName") or t.get("name", ""),
            "short_name": t.get("abbreviation") or t.get("shortDisplayName", ""),
            "logo_url":   logo_url,
        })

    df = pd.DataFrame(records)
    logger.info("ESPN teams: %d fetched for %s", len(df), league_id)
    return df


# ── Scoreboard / fixtures ──────────────────────────────────────────────────

def fetch_scoreboard(league_id: str) -> pd.DataFrame:
    """Fetch current/recent events for a league."""
    espn_id = ESPN_LEAGUE_IDS.get(league_id)
    if not espn_id:
        return pd.DataFrame()

    data = _get(f"{ESPN_BASE}/{espn_id}/scoreboard")
    if not data:
        return pd.DataFrame()

    events = data.get("events", [])
    if not events:
        logger.info("ESPN scoreboard: 0 events for %s", league_id)
        return pd.DataFrame()

    records = []
    for event in events:
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors", [])
        if len(competitors) < 2:
            continue

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        raw_status = (
            competition.get("status", {})
                       .get("type", {})
                       .get("name", "scheduled")
                       .lower()
        )
        if "final" in raw_status or "post" in raw_status:
            status = "final"
        elif "in" in raw_status or "progress" in raw_status:
            status = "live"
        else:
            status = "scheduled"

        # Use ESPN numeric team IDs — slug not present on scoreboard competitors
        h_eid = str(home.get("team", {}).get("id", ""))
        a_eid = str(away.get("team", {}).get("id", ""))
        venue = competition.get("venue") or {}

        records.append({
            "id":            str(event.get("id", "")),
            "espn_event_id": str(event.get("id", "")),
            "league_id":     league_id,
            "home_team_id":  f"{league_id}-{h_eid}",
            "away_team_id":  f"{league_id}-{a_eid}",
            "kickoff_utc":   event.get("date", ""),
            "home_score":    int(home.get("score") or 0),
            "away_score":    int(away.get("score") or 0),
            "home_tries":    0,
            "away_tries":    0,
            "status":        status,
            "venue":         venue.get("fullName") or venue.get("name", ""),
            "round":         int((event.get("week") or {}).get("number") or 0),
            "home_form":     home.get("form", ""),
            "away_form":     away.get("form", ""),
        })

    logger.info("ESPN scoreboard: %d events for %s", len(records), league_id)
    return pd.DataFrame(records)


# ── Standings (via event summary — the /standings endpoint is broken) ──────

def fetch_standings(league_id: str, event_id: str | None = None) -> pd.DataFrame:
    """Fetch standings embedded in an event summary.

    ESPN's /standings endpoint returns only {"fullViewLink": ...} for rugby.
    Standings data is available inside the /summary?event= response instead.
    """
    espn_id = ESPN_LEAGUE_IDS.get(league_id)
    if not espn_id:
        return pd.DataFrame()

    if not event_id:
        # Pull one event id from the scoreboard
        sb = _get(f"{ESPN_BASE}/{espn_id}/scoreboard")
        if not sb:
            return pd.DataFrame()
        events = sb.get("events", [])
        if not events:
            logger.info("ESPN standings: no events available for %s — skipping", league_id)
            return pd.DataFrame()
        event_id = str(events[0].get("id", ""))

    data = _get(f"{ESPN_BASE}/{espn_id}/summary", params={"event": event_id})
    if not data:
        return pd.DataFrame()

    standings_root = data.get("standings", {})
    # Entries can live directly in standings_root or under children[n]
    children = standings_root.get("children", [standings_root])
    season = datetime.now().year

    records = []
    for child in children:
        for entry in (child.get("standings") or child).get("entries", []):
            team     = entry.get("team", {})
            espn_tid = str(team.get("id", ""))
            if not espn_tid:
                continue
            stats = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
            gp    = max(1, int(stats.get("gamesPlayed", 1)))
            records.append({
                "team_id":        f"{league_id}-{espn_tid}",
                "league_id":      league_id,
                "season":         season,
                "played":         int(stats.get("gamesPlayed", 0)),
                "won":            int(stats.get("wins", 0)),
                "lost":           int(stats.get("losses", 0)),
                "drawn":          int(stats.get("ties", 0)),
                # Derive totals from per-game averages
                "points_for":     round(float(stats.get("avgPointsFor",     0)) * gp),
                "points_against": round(float(stats.get("avgPointsAgainst", 0)) * gp),
                "tries_for":      int(stats.get("triesFor",      0)),
                "tries_against":  int(stats.get("triesAgainst",  0)),
                "bonus_points":   int(stats.get("bonusPoints",   0)),
                "league_points":  int(stats.get("points",        0)),
                "ppg":            round(float(stats.get("avgPointsFor",     0)), 2),
                "opp_ppg":        round(float(stats.get("avgPointsAgainst", 0)), 2),
            })

    if not records:
        logger.info("ESPN standings: no entries for %s", league_id)
        return pd.DataFrame()

    logger.info("ESPN standings: %d teams for %s", len(records), league_id)
    return pd.DataFrame(records)


# ── Match player stats ─────────────────────────────────────────────────────

def fetch_match_stats(event_id: str, league_id: str) -> pd.DataFrame:
    """Fetch player-level stats for a completed match.

    ESPN rugby player stats live in rosters[].roster[].stats (not boxscore).
    Each roster entry has a flat list of {name, value} stat dicts.
    """
    espn_id = ESPN_LEAGUE_IDS.get(league_id)
    if not espn_id:
        return pd.DataFrame()

    data = _get(f"{ESPN_BASE}/{espn_id}/summary", params={"event": event_id})
    if not data:
        return pd.DataFrame()

    rosters = data.get("rosters", [])
    if not rosters:
        logger.debug("ESPN match stats: no roster data for event %s league %s", event_id, league_id)
        return pd.DataFrame()

    records = []
    for team_entry in rosters:
        t_id    = str(team_entry.get("team", {}).get("id", ""))
        team_id = f"{league_id}-{t_id}"
        is_home = team_entry.get("homeAway") == "home"

        for player in team_entry.get("roster", []):
            a      = player.get("athlete", {})
            pid    = str(a.get("id", ""))
            if not pid:
                continue
            pos    = player.get("position", {}) or {}
            sm     = {s["name"]: float(s.get("value", 0) or 0)
                      for s in player.get("stats", []) if s.get("name")}

            records.append({
                "id":             f"{event_id}-{pid}",
                "match_id":       str(event_id),
                "player_id":      pid,
                "team_id":        team_id,
                "league_id":      league_id,
                "player_name":    a.get("displayName", ""),
                "position":       pos.get("abbreviation", ""),
                "is_starter":     int(bool(player.get("starter"))),
                "is_home":        int(is_home),
                "tries":          int(sm.get("tries",            0)),
                "assists":        int(sm.get("tryAssists",        0)),
                "carries":        int(sm.get("runs",              0)),
                "metres_run":     int(sm.get("metres",            0)),
                "tackles":        int(sm.get("tackles",           0)),
                "missed_tackles": int(sm.get("missedTackles",     0)),
                "linebreaks":     int(sm.get("cleanBreaks",       0)),
                "defenders_beaten": int(sm.get("defendersBeaten", 0)),
                "offloads":       int(sm.get("offload",           0)),
                "turnovers":      int(sm.get("turnoversConceded", 0)),
                "points":         int(sm.get("points",            0)),
                "minutes_played": 80,  # ESPN doesn't provide per-player minutes
            })

    if not records:
        logger.debug("ESPN match stats: no player rows for event %s", event_id)
    else:
        logger.debug("ESPN match stats: %d players for event %s", len(records), event_id)
    return pd.DataFrame(records)
