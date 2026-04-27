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
