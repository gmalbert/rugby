"""
ScrumBet data pipeline.

Orchestrates all scrapers → writes CSV / Parquet data files.
Run nightly via GitHub Actions (see .github/workflows/scrape.yml).

Usage:
    python data/pipeline.py
"""

import logging
import time
import sys
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

# Allow running as a script from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import CSV_DIR, PARQUET_DIR, LEAGUE_LIST, LEAGUES, ODDS_API_KEY, ODDS_API_BASE, ODDS_SPORT_MAP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── I/O helpers ────────────────────────────────────────────────────────────

def _ensure_dirs() -> None:
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)


def _save_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)
    logger.info("CSV  %-50s  %d rows", path.name, len(df))


def _upsert_csv(new: pd.DataFrame, path: Path, key: list[str]) -> pd.DataFrame:
    """Merge new rows into existing CSV, deduplicating on key columns."""
    if new.empty:
        return pd.read_csv(path) if path.exists() else new
    try:
        existing = pd.read_csv(path)
        merged   = (
            pd.concat([existing, new])
              .drop_duplicates(subset=key, keep="last")
              .reset_index(drop=True)
        )
    except FileNotFoundError:
        merged = new
    _save_csv(merged, path)
    return merged


def _append_parquet(new: pd.DataFrame, path: Path, key: list[str]) -> None:
    """Merge new rows into existing Parquet, deduplicating on key columns."""
    if new.empty:
        return
    try:
        existing = pd.read_parquet(path)
        combined = (
            pd.concat([existing, new])
              .drop_duplicates(subset=key, keep="last")
              .reset_index(drop=True)
        )
    except FileNotFoundError:
        combined = new
    combined.to_parquet(path, index=False)
    logger.info("PARQUET  %-46s  %d rows", path.name, len(combined))


# ── Scraper runners ────────────────────────────────────────────────────────

def _run_espn() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (matches_df, standings_df, teams_df) aggregated across all leagues."""
    from data.scrapers.espn_api import (
        fetch_scoreboard, fetch_standings, fetch_teams
    )

    all_matches, all_standings, all_teams = [], [], []

    for league_id in LEAGUE_LIST:
        logger.info("ESPN → %s", LEAGUES[league_id])
        t = fetch_teams(league_id)
        if not t.empty:
            all_teams.append(t)

        m = fetch_scoreboard(league_id)
        if not m.empty:
            all_matches.append(m)
            # Pull standings from the first event in the scoreboard response
            first_event_id = str(m.iloc[0].get("espn_event_id", m.iloc[0]["id"]))
            s = fetch_standings(league_id, event_id=first_event_id)
        else:
            s = fetch_standings(league_id)
        if not s.empty:
            all_standings.append(s)

        time.sleep(1)

    return (
        pd.concat(all_matches,   ignore_index=True) if all_matches   else pd.DataFrame(),
        pd.concat(all_standings, ignore_index=True) if all_standings else pd.DataFrame(),
        pd.concat(all_teams,     ignore_index=True) if all_teams     else pd.DataFrame(),
    )


def _run_worldrugby() -> pd.DataFrame:
    from data.scrapers.worldrugby import fetch_fixtures
    frames = []
    for lid in ("six_nations", "champions_cup"):
        f = fetch_fixtures(lid)
        if not f.empty:
            frames.append(f)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _fetch_player_stats(matches: pd.DataFrame) -> pd.DataFrame:
    from data.scrapers.espn_api import fetch_match_stats

    # Champions Cup event IDs from ESPN are old/historical and return 404 — skip them.
    # Only fetch stats for leagues where the summary endpoint works reliably.
    STATS_LEAGUES = {"six_nations", "premiership", "top14", "super_rugby", "urc"}

    final = (
        matches[
            (matches["status"] == "final") &
            (matches["league_id"].isin(STATS_LEAGUES))
        ]
        .tail(60)
    )
    logger.info("Fetching player stats for %d final matches…", len(final))

    frames = []
    fetched = 0
    skipped = 0
    for _, row in final.iterrows():
        stats = fetch_match_stats(str(row["id"]), row["league_id"])
        if not stats.empty:
            frames.append(stats)
            fetched += 1
        else:
            skipped += 1
        time.sleep(0.5)

    logger.info("Player stats: %d matches with data, %d empty", fetched, skipped)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _fetch_odds() -> pd.DataFrame:
    import requests

    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not set — skipping odds fetch")
        return pd.DataFrame()

    records  = []
    scraped  = datetime.now(timezone.utc).isoformat()

    for league_id, sport_key in ODDS_SPORT_MAP.items():
        try:
            r = requests.get(
                f"{ODDS_API_BASE}/sports/{sport_key}/odds",
                params={
                    "apiKey":       ODDS_API_KEY,
                    "regions":      "us",
                    "markets":      "h2h,spreads,totals",
                    "bookmakers":   "draftkings",
                    "oddsFormat":   "american",
                },
                timeout=15,
            )
            if r.status_code == 404:
                continue
            r.raise_for_status()
        except Exception as e:
            logger.warning("Odds API %s → %s", league_id, e)
            continue

        for event in r.json():
            mid = event.get("id")
            for book in event.get("bookmakers", []):
                if book.get("key") != "draftkings":
                    continue

                mkts = {m["key"]: m for m in book.get("markets", [])}
                h2h  = {o["name"]: o["price"] for o in mkts.get("h2h", {}).get("outcomes", [])}
                sprd = {o["name"]: o            for o in mkts.get("spreads", {}).get("outcomes", [])}
                tot  = {o["name"]: o            for o in mkts.get("totals",  {}).get("outcomes", [])}

                hn = event.get("home_team", "")
                an = event.get("away_team", "")

                records.append({
                    "match_id":         mid,
                    "scraped_at":       scraped,
                    "home_ml":          h2h.get(hn),
                    "away_ml":          h2h.get(an),
                    "spread_home":      sprd.get(hn, {}).get("point"),
                    "spread_home_odds": sprd.get(hn, {}).get("price"),
                    "total_line":       tot.get("Over", {}).get("point"),
                    "total_over_odds":  tot.get("Over", {}).get("price"),
                    "total_under_odds": tot.get("Under", {}).get("price"),
                })

    return pd.DataFrame(records)


def _update_elo(matches: pd.DataFrame) -> None:
    from models.elo import build_elo_history
    new_elo = build_elo_history(matches)
    if not new_elo.empty:
        _append_parquet(new_elo, PARQUET_DIR / "elo_ratings.parquet",
                        key=["team_id", "league_id", "date"])


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    _ensure_dirs()
    logger.info("=== ScrumBet Pipeline Start ===")

    # Teams
    matches_espn, standings_espn, teams_espn = _run_espn()

    teams_path = CSV_DIR / "teams.csv"
    teams_merged = _upsert_csv(teams_espn, teams_path, key=["id"])

    # Matches (ESPN + World Rugby)
    matches_wr   = _run_worldrugby()
    all_matches  = pd.concat(
        [f for f in [matches_espn, matches_wr] if not f.empty],
        ignore_index=True,
    )
    matches_path   = CSV_DIR / "matches.csv"
    matches_merged = _upsert_csv(all_matches, matches_path, key=["id"])

    # Team season stats
    if not standings_espn.empty:
        _append_parquet(standings_espn, PARQUET_DIR / "team_season_stats.parquet",
                        key=["team_id", "league_id", "season"])

    # Player stats (only for new final matches)
    if not matches_merged.empty:
        player_stats = _fetch_player_stats(matches_merged)
        if not player_stats.empty:
            _append_parquet(player_stats, PARQUET_DIR / "player_match_stats.parquet",
                            key=["id"])

    # Elo ratings
    if not matches_merged.empty:
        _update_elo(matches_merged)

    # Odds
    odds_new = _fetch_odds()
    if not odds_new.empty:
        odds_path = CSV_DIR / "odds_snapshots.csv"
        try:
            from datetime import timedelta
            existing = pd.read_csv(odds_path, parse_dates=["scraped_at"])
            cutoff   = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
            existing = existing[existing["scraped_at"].astype(str) >= cutoff]
            odds_merged = (
                pd.concat([existing, odds_new])
                  .drop_duplicates(subset=["match_id", "scraped_at"], keep="last")
            )
        except FileNotFoundError:
            odds_merged = odds_new
        _save_csv(odds_merged, odds_path)

    logger.info("=== ScrumBet Pipeline Complete ===")


if __name__ == "__main__":
    main()
