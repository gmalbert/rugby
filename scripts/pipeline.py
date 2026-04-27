"""
ScrumBet data pipeline.

Orchestrates all scrapers → writes CSV / Parquet data files.
Run nightly via GitHub Actions (see .github/workflows/scrape.yml).

Usage:
    python scripts/pipeline.py
"""

import logging
import time
import sys
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

# Allow running as a script from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import CSV_DIR, PARQUET_DIR, LEAGUE_LIST, LEAGUES, ODDS_API_KEY, ODDS_API_BASE, ODDS_SPORT_MAP, ODDS_API_IO_KEY, ODDS_API_IO_RUGBY_LEAGUES, ODDS_API_IO_BOOKMAKERS

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
    from scripts.scrapers.espn_api import (
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
    from scripts.scrapers.worldrugby import fetch_fixtures
    frames = []
    for lid in ("six_nations", "champions_cup"):
        f = fetch_fixtures(lid)
        if not f.empty:
            frames.append(f)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _fetch_player_stats(matches: pd.DataFrame) -> pd.DataFrame:
    from scripts.scrapers.espn_api import fetch_match_stats

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
    """Fetch from the-odds-api.com (Six Nations only, when active)."""
    import requests

    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not set — skipping the-odds-api.com fetch")
        return pd.DataFrame()

    records  = []
    scraped  = datetime.now(timezone.utc).isoformat()
    skipped_inactive = []

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
                skipped_inactive.append(league_id)
                continue
            r.raise_for_status()
        except Exception as e:
            logger.warning("the-odds-api.com %s → %s", league_id, e)
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
                    "bookmaker":        "DraftKings",
                    "source":           "the-odds-api",
                })

    if skipped_inactive:
        logger.info(
            "the-odds-api.com: %d sport(s) inactive/off-season: %s",
            len(skipped_inactive), ", ".join(skipped_inactive),
        )
    logger.info("the-odds-api.com scraped: %d records", len(records))
    return pd.DataFrame(records)


def _fetch_odds_api_io(
    matches: pd.DataFrame,
    teams: pd.DataFrame,
) -> pd.DataFrame:
    """
    Fetch odds from odds-api.io for upcoming rugby matches.

    Matches odds-api.io events to our ESPN match IDs by normalised team name
    + date proximity (±1 day), then fetches DraftKings and BetMGM BR odds.

    Markets stored per row (American odds):
      home_ml / away_ml       — from DraftKings (or BetMGM BR as fallback)
      spread_home / spread_home_odds — from BetMGM BR, main handicap line
      total_line / total_over_odds / total_under_odds — from BetMGM BR

    Coverage confirmed (April 2026):
      - DraftKings: Super Rugby Union ML, NRL Premiership ML
      - BetMGM BR:  International rugby (U20 Rugby Championship etc.) —
                    ML, Spread, Totals, HT/FT, European Handicap
      - Neither bookmaker covers: Premiership Rugby, Top 14, URC,
        Champions Cup, or Six Nations (on the free plan)
    """
    import urllib.error
    from utils.odds_api_io import (
        get_events, get_odds,
        decimal_to_american, extract_market,
        main_spread_line, main_totals_line,
        names_match,
    )

    if not ODDS_API_IO_KEY:
        logger.warning("ODDS_API_IO_KEY not set — skipping odds-api.io fetch")
        return pd.DataFrame()

    # Build a fast team-id → name lookup
    if not teams.empty and "id" in teams.columns and "name" in teams.columns:
        tmap = dict(zip(teams["id"].astype(str), teams["name"]))
    else:
        tmap = {}

    def _tname(tid: str) -> str:
        return tmap.get(str(tid), str(tid))

    # Only consider upcoming matches (next 14 days)
    from datetime import timedelta
    from datetime import datetime as _dt
    now = _dt.now(timezone.utc)

    if not matches.empty:
        upcoming = matches.copy()
        if "kickoff_utc" in upcoming.columns:
            upcoming["kickoff_utc"] = pd.to_datetime(upcoming["kickoff_utc"], utc=True, errors="coerce")
        upcoming = upcoming[upcoming.get("status", pd.Series(dtype=str)) == "scheduled"]
    else:
        upcoming = pd.DataFrame()

    if "kickoff_utc" in upcoming.columns and not upcoming.empty:
        upcoming = upcoming[
            upcoming["kickoff_utc"].notna() &
            (upcoming["kickoff_utc"] >= now) &
            (upcoming["kickoff_utc"] <= now + timedelta(days=14))
        ]

    scraped = now.isoformat()
    records: list[dict] = []
    total_events = 0
    matched = 0
    no_odds = 0

    for league_id, api_slug in ODDS_API_IO_RUGBY_LEAGUES.items():
        try:
            events = get_events(
                "rugby", league=api_slug, status="pending,live", limit=50
            )
        except Exception as exc:
            logger.warning("odds-api.io get_events %s → %s", api_slug, exc)
            continue

        total_events += len(events)

        for ev in events:
            # ── Match to our ESPN match ID ────────────────────────────────
            our_match_id = None
            if not upcoming.empty:
                api_date = pd.Timestamp(ev["date"]).normalize()
                api_home = ev.get("home", "")
                api_away = ev.get("away", "")

                for _, m in upcoming.iterrows():
                    ko = m["kickoff_utc"]
                    if pd.isna(ko):
                        continue
                    if abs((pd.Timestamp(ko).normalize() - api_date).days) > 1:
                        continue
                    if (names_match(api_home, _tname(m["home_team_id"])) and
                            names_match(api_away, _tname(m["away_team_id"]))):
                        our_match_id = str(m["id"])
                        break

            if our_match_id is None:
                # Still store odds so the UI can show them unlinked
                our_match_id = f"api_io_{ev['id']}"

            # ── Fetch odds ────────────────────────────────────────────────
            try:
                odds_resp = get_odds(ev["id"], ODDS_API_IO_BOOKMAKERS)
            except urllib.error.HTTPError as e:
                logger.debug("odds-api.io get_odds %s event %s → HTTP %s", api_slug, ev["id"], e.code)
                no_odds += 1
                continue
            except Exception as exc:
                logger.debug("odds-api.io get_odds %s event %s → %s", api_slug, ev["id"], exc)
                no_odds += 1
                continue

            bm_data = odds_resp.get("bookmakers", {})
            if not bm_data:
                no_odds += 1
                continue

            row: dict = {
                "match_id":         our_match_id,
                "scraped_at":       scraped,
                "home_ml":          None,
                "away_ml":          None,
                "spread_home":      None,
                "spread_home_odds": None,
                "total_line":       None,
                "total_over_odds":  None,
                "total_under_odds": None,
                "bookmaker":        None,
                "source":           "odds-api-io",
            }

            for bname in ["DraftKings", "BetMGM BR"]:
                if bname not in bm_data:
                    continue
                mkts = bm_data[bname]

                ml = extract_market(mkts, "ML")
                if ml and row["home_ml"] is None:
                    o = ml[0]
                    if o.get("home"):
                        row["home_ml"] = decimal_to_american(float(o["home"]))
                    if o.get("away"):
                        row["away_ml"] = decimal_to_american(float(o["away"]))
                    row["bookmaker"] = bname

                sp = extract_market(mkts, "Spread")
                if sp and row["spread_home"] is None:
                    main_sp = main_spread_line(sp)
                    if main_sp:
                        row["spread_home"]      = float(main_sp.get("hdp", 0))
                        row["spread_home_odds"] = decimal_to_american(float(main_sp.get("home", 1.91)))

                tot = extract_market(mkts, "Totals")
                if tot and row["total_line"] is None:
                    main_tot = main_totals_line(tot)
                    if main_tot:
                        row["total_line"]       = float(main_tot.get("hdp", 0))
                        row["total_over_odds"]  = decimal_to_american(float(main_tot.get("over", 1.91)))
                        row["total_under_odds"] = decimal_to_american(float(main_tot.get("under", 1.91)))

            if row["home_ml"] is not None:
                records.append(row)
                if not our_match_id.startswith("api_io_"):
                    matched += 1

    logger.info(
        "odds-api.io: %d API events → %d with odds → %d linked to ESPN match IDs",
        total_events, len(records), matched,
    )
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
    matches_wr  = _run_worldrugby()
    all_matches = pd.concat(
        [f for f in [matches_espn, matches_wr] if not f.empty],
        ignore_index=True,
    )
    # Deduplicate within the batch before upsert (same event can come from multiple scrapers)
    if not all_matches.empty:
        all_matches = all_matches.drop_duplicates(subset=["id"], keep="last")
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

    # Odds — merge from both sources
    odds_frames = []
    odds_old = _fetch_odds()                                    # the-odds-api.com (Six Nations)
    if not odds_old.empty:
        odds_frames.append(odds_old)
    odds_new = _fetch_odds_api_io(matches_merged, teams_merged)  # odds-api.io (Super Rugby, NRL, etc.)
    if not odds_new.empty:
        odds_frames.append(odds_new)

    if odds_frames:
        combined_odds = pd.concat(odds_frames, ignore_index=True)
        odds_path = CSV_DIR / "odds_snapshots.csv"
        try:
            from datetime import timedelta
            existing = pd.read_csv(odds_path, parse_dates=["scraped_at"])
            cutoff   = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
            existing = existing[existing["scraped_at"].astype(str) >= cutoff]
            odds_merged = (
                pd.concat([existing, combined_odds])
                  .drop_duplicates(subset=["match_id", "scraped_at"], keep="last")
            )
        except FileNotFoundError:
            odds_merged = combined_odds
        _save_csv(odds_merged, odds_path)

    # Precompute models for fast Streamlit cold-start
    if not matches_merged.empty:
        _precompute_models(matches_merged, teams_merged)

    logger.info("=== ScrumBet Pipeline Complete ===")


def _precompute_models(matches: pd.DataFrame, teams: pd.DataFrame) -> None:
    """Fit models on all final data and save parquet artefacts for Streamlit to load instantly."""
    final = matches[matches["status"] == "final"].copy()
    logger.info("Precomputing models on %d final matches…", len(final))

    # ── Bradley-Terry ratings ──────────────────────────────────────────────
    if len(final) >= 5:
        try:
            import models.bradley_terry as bt
            model = bt.fit(final)
            if model:
                bt_df = bt.ratings_df(model, teams)
                bt_df.to_parquet(PARQUET_DIR / "bradley_terry_ratings.parquet", index=False)
                logger.info("Bradley-Terry saved (%d teams)", len(bt_df))
        except Exception as exc:
            logger.warning("Bradley-Terry fit failed: %s", exc)

    # ── Dixon-Coles parameters ─────────────────────────────────────────────
    if len(final) >= 15:
        try:
            import models.dixon_coles as dc
            model = dc.fit(final)
            if model:
                params_df = dc.params_df(model, teams)
                params_df.to_parquet(PARQUET_DIR / "dc_params.parquet", index=False)
                logger.info("Dixon-Coles params saved (%d teams)", len(params_df))
        except Exception as exc:
            logger.warning("Dixon-Coles fit failed: %s", exc)

    # ── Precomputed win probabilities for upcoming matches ─────────────────
    from datetime import timezone
    matches["kickoff_utc"] = pd.to_datetime(matches["kickoff_utc"], utc=True, errors="coerce")
    upcoming = matches[
        (matches["status"] == "scheduled") &
        (matches["kickoff_utc"] >= pd.Timestamp.now(tz=timezone.utc))
    ].copy()

    if upcoming.empty or final.empty:
        return

    try:
        from models.elo import build_elo_history, current_ratings, win_probability as elo_wp
        elo_history = build_elo_history(final)
        ratings     = current_ratings(elo_history).to_dict()

        rows = []
        for _, row in upcoming.iterrows():
            h, a  = str(row["home_team_id"]), str(row["away_team_id"])
            ph, pd_draw, pa = elo_wp(ratings.get(h, 1500), ratings.get(a, 1500))
            rows.append({
                "match_id":       str(row["id"]),
                "league_id":      row.get("league_id", ""),
                "home_team_id":   h,
                "away_team_id":   a,
                "kickoff_utc":    row.get("kickoff_utc"),
                "elo_home_prob":  round(ph, 4),
                "elo_draw_prob":  round(pd_draw, 4),
                "elo_away_prob":  round(pa, 4),
            })

        if rows:
            pred_df = pd.DataFrame(rows)
            pred_df.to_parquet(PARQUET_DIR / "precomputed_predictions.parquet", index=False)
            logger.info("Precomputed predictions saved (%d fixtures)", len(pred_df))
    except Exception as exc:
        logger.warning("Win-prob precompute failed: %s", exc)


if __name__ == "__main__":
    main()
