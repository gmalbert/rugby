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
