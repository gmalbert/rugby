"""Cached data-loading functions for Streamlit pages."""

import streamlit as st
import pandas as pd
from utils.config import CSV_DIR, PARQUET_DIR

# ── Empty-schema helpers ───────────────────────────────────────────────────

_MATCH_COLS   = ["id", "league_id", "home_team_id", "away_team_id",
                 "kickoff_utc", "home_score", "away_score",
                 "home_tries", "away_tries", "status", "venue", "round"]
_TEAM_COLS    = ["id", "league_id", "name", "short_name", "logo_url"]
_LEAGUE_COLS  = ["id", "name", "espn_id", "season"]
_ODDS_COLS    = ["match_id", "scraped_at", "home_ml", "away_ml",
                 "spread_home", "spread_home_odds",
                 "total_line", "total_over_odds", "total_under_odds"]
_PLAYER_COLS  = ["id", "match_id", "player_id", "team_id", "player_name",
                 "position", "tries", "assists", "carries", "metres_run",
                 "tackles", "missed_tackles", "linebreaks", "minutes_played"]
_TSS_COLS     = ["team_id", "league_id", "season", "played", "won", "lost",
                 "drawn", "points_for", "points_against", "tries_for",
                 "tries_against", "bonus_points", "league_points"]
_ELO_COLS     = ["team_id", "league_id", "date", "rating"]


# ── CSV loaders ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_leagues() -> pd.DataFrame:
    p = CSV_DIR / "leagues.csv"
    if not p.exists():
        return pd.DataFrame(columns=_LEAGUE_COLS)
    return pd.read_csv(p)


@st.cache_data(ttl=3600)
def load_teams() -> pd.DataFrame:
    p = CSV_DIR / "teams.csv"
    if not p.exists():
        return pd.DataFrame(columns=_TEAM_COLS)
    return pd.read_csv(p)


@st.cache_data(ttl=300)
def load_matches() -> pd.DataFrame:
    p = CSV_DIR / "matches.csv"
    if not p.exists():
        return pd.DataFrame(columns=_MATCH_COLS)
    df = pd.read_csv(p)
    if "kickoff_utc" in df.columns:
        df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True, errors="coerce")
    # Normalise id to str so it always joins cleanly with player parquet match_id
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
    # Pipeline may write the same match from multiple scrapers — keep one row per id
    df = df.drop_duplicates(subset="id", keep="last")
    return df


@st.cache_data(ttl=300)
def load_odds() -> pd.DataFrame:
    p = CSV_DIR / "odds_snapshots.csv"
    if not p.exists():
        return pd.DataFrame(columns=_ODDS_COLS)
    df = pd.read_csv(p)
    if "scraped_at" in df.columns:
        df["scraped_at"] = pd.to_datetime(df["scraped_at"], utc=True, errors="coerce")
    return df


# ── Parquet loaders ────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def load_player_stats() -> pd.DataFrame:
    p = PARQUET_DIR / "player_match_stats.parquet"
    if not p.exists():
        return pd.DataFrame(columns=_PLAYER_COLS)
    return pd.read_parquet(p)


@st.cache_data(ttl=3600)
def load_team_season_stats() -> pd.DataFrame:
    p = PARQUET_DIR / "team_season_stats.parquet"
    if not p.exists():
        return pd.DataFrame(columns=_TSS_COLS)
    return pd.read_parquet(p)


@st.cache_data(ttl=3600)
def load_elo_ratings() -> pd.DataFrame:
    p = PARQUET_DIR / "elo_ratings.parquet"
    if not p.exists():
        return pd.DataFrame(columns=_ELO_COLS)
    df = pd.read_parquet(p)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ── Precomputed model outputs (written by pipeline) ────────────────────────

_PRED_COLS = [
    "match_id", "home_team_id", "away_team_id", "league_id",
    "elo_p_home", "elo_p_draw", "elo_p_away",
    "dc_p_home", "dc_p_draw", "dc_p_away",
    "dc_exp_home", "dc_exp_away",
]

_BT_COLS = ["team_id", "league_id", "bt_strength"]

_DC_PARAM_COLS = ["team_id", "team", "attack", "defence"]


@st.cache_data(ttl=3600)
def load_precomputed_predictions() -> pd.DataFrame:
    """Upcoming fixture win probabilities from Elo + DC, precomputed by pipeline."""
    p = PARQUET_DIR / "precomputed_predictions.parquet"
    if not p.exists():
        return pd.DataFrame(columns=_PRED_COLS)
    return pd.read_parquet(p)


@st.cache_data(ttl=3600)
def load_bradley_terry_ratings() -> pd.DataFrame:
    """Bradley-Terry team strength ratings, precomputed by pipeline."""
    p = PARQUET_DIR / "bradley_terry_ratings.parquet"
    if not p.exists():
        return pd.DataFrame(columns=_BT_COLS)
    return pd.read_parquet(p)


@st.cache_data(ttl=3600)
def load_dc_params() -> pd.DataFrame:
    """Dixon-Coles attack/defence parameters, precomputed by pipeline."""
    p = PARQUET_DIR / "dc_params.parquet"
    if not p.exists():
        return pd.DataFrame(columns=_DC_PARAM_COLS)
    return pd.read_parquet(p)


@st.cache_data(ttl=3600, show_spinner="Fitting Dixon-Coles model…")
def fit_dc_cached(matches_hash: int, matches_df: pd.DataFrame) -> dict | None:
    """Cached Dixon-Coles fitting.  Pass hash of matches_df as first arg for cache keying."""
    import models.dixon_coles as dc
    final = matches_df[matches_df["status"] == "final"]
    if len(final) < 15:
        return None
    return dc.fit(final)


@st.cache_data(ttl=3600, show_spinner="Fitting Bradley-Terry model…")
def fit_bt_cached(matches_hash: int, matches_df: pd.DataFrame) -> dict | None:
    """Cached Bradley-Terry fitting."""
    import models.bradley_terry as bt
    return bt.fit(matches_df)


@st.cache_data(ttl=3600, show_spinner="Training try-scorer model…")
def fit_try_scorer_cached(
    data_hash: int, player_df: pd.DataFrame, matches_df: pd.DataFrame
) -> object | None:
    """Cached try-scorer model training."""
    from models.try_scorer import build_features, train
    final = matches_df[matches_df["status"] == "final"]
    if len(final) < 20 or player_df.empty:
        return None
    features = build_features(player_df, final)
    if features.empty:
        return None
    return train(features)


# ── Live odds from odds-api.io (bypasses pipeline CSV, 5-min TTL) ─────────

_LIVE_ODDS_COLS = [
    "api_event_id", "api_league_slug", "league_id",
    "home_name", "away_name", "kickoff_utc", "scraped_at",
    "home_ml", "away_ml",
    "spread_home", "spread_home_odds",
    "total_line", "total_over_odds", "total_under_odds",
    "bookmaker",
]


_ODDS_API_IO_MAX_AGE_HOURS = 6  # treat pipeline CSV as fresh if scraped within this window


@st.cache_data(ttl=3600, show_spinner=False)
def load_live_rugby_odds() -> pd.DataFrame:
    """
    Return odds-api.io odds for upcoming rugby events.

    Strategy (API-budget-friendly):
    1. Read rows with source='odds-api-io' from odds_snapshots.csv (written by the
       nightly pipeline / GH Actions). If the most recent scrape is < 6 hours old,
       return those rows directly — no API call is made.
    2. Only if the CSV is missing or stale does this function call the odds-api.io
       API directly. This keeps page-load API usage near zero for normal operation.

    The Streamlit cache TTL is 1 hour so that a stale fallback isn't re-fetched
    constantly, while still refreshing within the day if the pipeline hasn't run.
    """
    from datetime import datetime, timezone, timedelta
    import urllib.error

    from utils.config import ODDS_API_IO_KEY, ODDS_API_IO_RUGBY_LEAGUES, ODDS_API_IO_BOOKMAKERS
    from utils.odds_api_io import (
        get_events, get_odds,
        decimal_to_american, extract_market,
        main_spread_line, main_totals_line,
    )

    now = datetime.now(timezone.utc)

    # ── Step 1: Try the pipeline CSV ─────────────────────────────────────
    csv_path = CSV_DIR / "odds_snapshots.csv"
    if csv_path.exists():
        raw = pd.read_csv(csv_path, dtype=str)
        if "source" in raw.columns:
            io_rows = raw[raw["source"] == "odds-api-io"].copy()
            if not io_rows.empty:
                io_rows["scraped_at"] = pd.to_datetime(io_rows["scraped_at"], utc=True, errors="coerce")
                most_recent = io_rows["scraped_at"].max()
                if pd.notna(most_recent) and (now - most_recent) < timedelta(hours=_ODDS_API_IO_MAX_AGE_HOURS):
                    # CSV is fresh — reshape to _LIVE_ODDS_COLS and return
                    for col in _LIVE_ODDS_COLS:
                        if col not in io_rows.columns:
                            io_rows[col] = None
                    if "kickoff_utc" in io_rows.columns:
                        io_rows["kickoff_utc"] = pd.to_datetime(io_rows["kickoff_utc"], utc=True, errors="coerce")
                    return io_rows[[c for c in _LIVE_ODDS_COLS if c in io_rows.columns]]

    # ── Step 2: CSV missing/stale — call API directly ────────────────────
    if not ODDS_API_IO_KEY:
        return pd.DataFrame(columns=_LIVE_ODDS_COLS)

    records: list[dict] = []
    scraped = now.isoformat()

    for league_id, api_slug in ODDS_API_IO_RUGBY_LEAGUES.items():
        try:
            events = get_events("rugby", league=api_slug, status="pending,live", limit=50)
        except Exception:
            continue

        for ev in events:
            try:
                odds_resp = get_odds(ev["id"], ODDS_API_IO_BOOKMAKERS)
            except (urllib.error.HTTPError, Exception):
                continue

            bm_data = odds_resp.get("bookmakers", {})
            if not bm_data:
                continue

            row: dict = {
                "api_event_id":     ev["id"],
                "api_league_slug":  api_slug,
                "league_id":        league_id,
                "home_name":        ev.get("home", ""),
                "away_name":        ev.get("away", ""),
                "kickoff_utc":      ev.get("date", ""),
                "scraped_at":       scraped,
                "home_ml":          None,
                "away_ml":          None,
                "spread_home":      None,
                "spread_home_odds": None,
                "total_line":       None,
                "total_over_odds":  None,
                "total_under_odds": None,
                "bookmaker":        None,
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
                    main = main_spread_line(sp)
                    if main:
                        row["spread_home"]      = float(main.get("hdp", 0))
                        row["spread_home_odds"] = decimal_to_american(float(main.get("home", 1.91)))

                tot = extract_market(mkts, "Totals")
                if tot and row["total_line"] is None:
                    main = main_totals_line(tot)
                    if main:
                        row["total_line"]       = float(main.get("hdp", 0))
                        row["total_over_odds"]  = decimal_to_american(float(main.get("over", 1.91)))
                        row["total_under_odds"] = decimal_to_american(float(main.get("under", 1.91)))

            if row["home_ml"] is not None:
                records.append(row)

    df = pd.DataFrame(records, columns=_LIVE_ODDS_COLS) if records else pd.DataFrame(columns=_LIVE_ODDS_COLS)
    if "kickoff_utc" in df.columns and not df.empty:
        df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True, errors="coerce")
    return df
