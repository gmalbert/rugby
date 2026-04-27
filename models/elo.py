"""
Elo rating system for rugby match outcome prediction.

K = 32, HOME_ADV = 50 Elo points for home team.
Margin-of-victory weighting: larger wins move the needle more.
"""

import pandas as pd
import numpy as np
from utils.config import ELO_K, ELO_HOME_ADV, ELO_DEFAULT


# ── Core Elo maths ─────────────────────────────────────────────────────────

def expected_score(rating_a: float, rating_b: float) -> float:
    """Logistic expected score for player A vs player B."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def _mov_multiplier(point_diff: int) -> float:
    """
    Margin-of-victory multiplier.
    Logarithmic scaling common in rugby Elo models.
    """
    return np.log(abs(point_diff) + 1) + 1.0


def update_elo(
    rating_a: float,
    rating_b: float,
    result_a: float,       # 1 = win, 0.5 = draw, 0 = loss
    home: bool = True,
    point_diff: int = 0,
    use_mov: bool = True,
) -> tuple[float, float]:
    ra = rating_a + (ELO_HOME_ADV if home else 0)
    exp = expected_score(ra, rating_b)
    k = ELO_K * (_mov_multiplier(point_diff) if use_mov and point_diff else 1.0)
    new_a = rating_a + k * (result_a - exp)
    new_b = rating_b + k * ((1 - result_a) - (1 - exp))
    return new_a, new_b


def win_probability(
    rating_home: float, rating_away: float
) -> tuple[float, float, float]:
    """
    Returns (p_home_win, p_draw, p_away_win).
    Draw probability is approximated; rugby has few draws.
    """
    ra = rating_home + ELO_HOME_ADV
    p_home_raw = expected_score(ra, rating_away)
    # Small draw probability, shrinks as rating gap grows
    p_draw = max(0.03, 0.10 - abs(p_home_raw - 0.5) * 0.25)
    p_home = p_home_raw - p_draw / 2
    p_away = 1 - p_home - p_draw
    return max(0.01, p_home), max(0.01, p_draw), max(0.01, p_away)


# ── History builder ────────────────────────────────────────────────────────

def build_elo_history(
    matches: pd.DataFrame,
    initial_ratings: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Process all final matches in chronological order.

    Returns a DataFrame with columns: team_id, league_id, date, rating
    (one row per team per match date).
    """
    if matches.empty:
        return pd.DataFrame(columns=["team_id", "league_id", "date", "rating"])

    ratings = dict(initial_ratings or {})
    records: list[dict] = []

    df = (
        matches[matches["status"] == "final"]
        .sort_values("kickoff_utc")
        .dropna(subset=["home_score", "away_score"])
        .copy()
    )

    for _, row in df.iterrows():
        h_id  = row["home_team_id"]
        a_id  = row["away_team_id"]
        league = row["league_id"]

        r_h = ratings.get(h_id, ELO_DEFAULT)
        r_a = ratings.get(a_id, ELO_DEFAULT)

        h_score = int(row["home_score"])
        a_score = int(row["away_score"])
        diff    = h_score - a_score

        if diff > 0:
            result = 1.0
        elif diff == 0:
            result = 0.5
        else:
            result = 0.0

        new_h, new_a = update_elo(r_h, r_a, result, home=True, point_diff=diff)
        ratings[h_id] = new_h
        ratings[a_id] = new_a

        match_date = pd.Timestamp(row["kickoff_utc"]).date()
        records.append({"team_id": h_id, "league_id": league, "date": match_date, "rating": round(new_h, 2)})
        records.append({"team_id": a_id, "league_id": league, "date": match_date, "rating": round(new_a, 2)})

    return pd.DataFrame(records)


def current_ratings(elo_df: pd.DataFrame) -> pd.Series:
    """Return the most recent Elo rating per team_id."""
    if elo_df.empty:
        return pd.Series(dtype=float)
    return (
        elo_df.sort_values("date")
              .groupby("team_id")["rating"]
              .last()
    )
