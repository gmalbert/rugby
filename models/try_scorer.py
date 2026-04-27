"""
Try-scorer probability model.

Logistic regression: P(player scores ≥1 try in match).
Features: tries_per_80, avg_minutes, opp_tries_conceded_pg,
          is_starter, is_home, position_encoded, form_last3.
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import brier_score_loss

FEATURE_COLS = [
    "tries_per_80",
    "avg_minutes",
    "opp_tries_conceded_pg",
    "is_starter",
    "is_home",
    "position_encoded",
    "form_last3",
]


# ── Feature engineering ────────────────────────────────────────────────────

def build_features(
    player_stats: pd.DataFrame,
    matches: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join player stats with match metadata and derive model features.
    Returns a DataFrame ready for train() / predict_proba().
    """
    if player_stats.empty or matches.empty:
        return pd.DataFrame()

    match_lookup = matches[
        ["id", "home_team_id", "away_team_id", "kickoff_utc", "league_id"]
    ].copy()

    df = player_stats.merge(
        match_lookup, left_on="match_id", right_on="id",
        how="left", suffixes=("", "_match")
    )

    # ── tries per 80 minutes (career average) ─────────────────────────────
    safe_mins = df["minutes_played"].clip(lower=1)
    df["tries_per_80_raw"] = df["tries"] / safe_mins * 80

    career_avg = (
        df.groupby("player_id")["tries_per_80_raw"]
          .mean()
          .rename("tries_per_80")
    )
    df = df.merge(career_avg, on="player_id")

    # ── avg minutes ────────────────────────────────────────────────────────
    avg_mins = (
        df.groupby("player_id")["minutes_played"]
          .mean()
          .rename("avg_minutes")
    )
    df = df.merge(avg_mins, on="player_id")

    # ── is_starter ─────────────────────────────────────────────────────────
    df["is_starter"] = (df["minutes_played"] >= 50).astype(int)

    # ── is_home ────────────────────────────────────────────────────────────
    df["is_home"] = (df["team_id"] == df["home_team_id"]).astype(int)

    # ── position encoding ──────────────────────────────────────────────────
    le = LabelEncoder()
    df["position_encoded"] = le.fit_transform(df["position"].fillna("Unknown"))

    # ── opponent tries-conceded per game ───────────────────────────────────
    opp_map = (
        df.groupby("team_id")["tries"]
          .mean()
          .rename("opp_tries_conceded_pg")
    )
    df = df.merge(
        opp_map, left_on="away_team_id", right_on="team_id",
        how="left", suffixes=("", "_opp")
    )
    df["opp_tries_conceded_pg"] = df["opp_tries_conceded_pg"].fillna(
        df["tries"].mean()
    )

    # ── recent form: rolling 3-game tries average ──────────────────────────
    df = df.sort_values("kickoff_utc")
    df["form_last3"] = (
        df.groupby("player_id")["tries"]
          .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
          .fillna(0)
    )

    # ── target ─────────────────────────────────────────────────────────────
    df["scored"] = (df["tries"] >= 1).astype(int)

    return df


# ── Training ───────────────────────────────────────────────────────────────

def train(df: pd.DataFrame) -> LogisticRegression | None:
    """Fit model and return it, or None if insufficient data."""
    if df.empty or len(df) < 30:
        return None

    required = FEATURE_COLS + ["scored"]
    if not all(c in df.columns for c in required):
        return None

    X = df[FEATURE_COLS].fillna(0)
    y = df["scored"]

    if y.nunique() < 2:
        return None

    model = LogisticRegression(max_iter=1000, C=1.0, class_weight="balanced")
    model.fit(X, y)
    return model


def evaluate(model: LogisticRegression, df: pd.DataFrame) -> dict:
    """Return basic accuracy metrics."""
    if model is None or df.empty:
        return {}
    X = df[FEATURE_COLS].fillna(0)
    y = df["scored"]
    probs = model.predict_proba(X)[:, 1]
    return {
        "brier_score": round(brier_score_loss(y, probs), 4),
        "n_samples":   len(df),
        "positive_rate": round(y.mean(), 3),
    }


# ── Single-player prediction ───────────────────────────────────────────────

def predict_player(
    player_id: str,
    opp_team_id: str,
    is_home: bool,
    player_stats: pd.DataFrame,
    model: LogisticRegression | None,
) -> float:
    """
    Predict P(anytime try scorer) for a specific player in an upcoming match.
    Returns probability in [0, 1].
    """
    if model is None or player_stats.empty:
        return 0.0

    rows = player_stats[player_stats["player_id"] == player_id]
    if rows.empty:
        return 0.0

    safe_mins = rows["minutes_played"].clip(lower=1)
    tries_per_80    = float((rows["tries"] / safe_mins * 80).mean())
    avg_minutes     = float(rows["minutes_played"].mean())
    is_starter      = int(avg_minutes >= 50)

    opp_rows        = player_stats[player_stats["team_id"] == opp_team_id]
    opp_td_pg       = float(opp_rows["tries"].mean()) if not opp_rows.empty else 2.0

    pos             = rows["position"].mode()
    pos_val         = abs(hash(pos.iloc[0])) % 15 if not pos.empty else 7
    form_last3      = float(rows.sort_values("match_id")["tries"].tail(3).mean())

    X = pd.DataFrame([{
        "tries_per_80":          tries_per_80,
        "avg_minutes":           avg_minutes,
        "opp_tries_conceded_pg": opp_td_pg,
        "is_starter":            is_starter,
        "is_home":               int(is_home),
        "position_encoded":      pos_val,
        "form_last3":            form_last3,
    }])

    try:
        return float(model.predict_proba(X[FEATURE_COLS].fillna(0))[0][1])
    except Exception:
        return 0.0


# ── Top scorers for a match ────────────────────────────────────────────────

def top_try_scorers_for_match(
    home_team_id: str,
    away_team_id: str,
    player_stats: pd.DataFrame,
    model: LogisticRegression | None,
    n: int = 5,
) -> pd.DataFrame:
    """Return top-n predicted try scorers for each team."""
    if model is None or player_stats.empty:
        return pd.DataFrame()

    records = []
    for team_id, opp_id, is_home in [
        (home_team_id, away_team_id, True),
        (away_team_id, home_team_id, False),
    ]:
        players = player_stats[player_stats["team_id"] == team_id][
            ["player_id", "player_name"]
        ].drop_duplicates("player_id")

        for _, p in players.iterrows():
            prob = predict_player(
                p["player_id"], opp_id, is_home, player_stats, model
            )
            records.append({
                "team_id":     team_id,
                "player_id":   p["player_id"],
                "player_name": p["player_name"],
                "prob":        prob,
                "is_home":     is_home,
            })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    return (
        df.sort_values("prob", ascending=False)
          .groupby("team_id")
          .head(n)
          .reset_index(drop=True)
    )
