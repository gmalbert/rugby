"""
Bradley-Terry pairwise comparison model for ScrumBet.

More statistically principled than Elo for round-robin competitions because it
estimates latent team strengths via maximum likelihood across the full fixture
list simultaneously rather than sequential updates.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit  # sigmoid


def fit(matches: pd.DataFrame, home_adv: bool = True) -> dict | None:
    """
    Fit a Bradley-Terry model to completed match results.

    Parameters
    ----------
    matches:
        DataFrame with columns home_team_id, away_team_id, home_score, away_score.
    home_adv:
        Whether to include a home-advantage parameter.

    Returns
    -------
    Dict with keys ``teams`` ({id: strength float}), ``home_adv`` (float),
    ``log_likelihood`` (float), or None if optimisation fails.
    """
    final = matches[matches["status"] == "final"] if "status" in matches.columns else matches
    if len(final) < 5:
        return None

    teams = sorted(set(final["home_team_id"]) | set(final["away_team_id"]))
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    def neg_log_likelihood(params: np.ndarray) -> float:
        strengths = params[:n]
        h = params[n] if home_adv else 0.0
        ll = 0.0
        for _, row in final.iterrows():
            hi = idx[row["home_team_id"]]
            ai = idx[row["away_team_id"]]
            p_home = expit(strengths[hi] - strengths[ai] + h)
            if row["home_score"] > row["away_score"]:
                ll += np.log(p_home + 1e-10)
            elif row["home_score"] < row["away_score"]:
                ll += np.log(1.0 - p_home + 1e-10)
            else:
                ll += np.log(0.5)
        return -ll

    x0 = np.zeros(n + (1 if home_adv else 0))
    bounds = [(None, None)] * n + ([(0.0, 3.0)] if home_adv else [])
    result = minimize(
        neg_log_likelihood,
        x0,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 1000},
    )
    if not result.success:
        return None

    params = result.x
    # Centre strengths so the mean is 0 (identifiability)
    strengths = params[:n]
    strengths -= strengths.mean()
    return {
        "teams":           {t: float(strengths[idx[t]]) for t in teams},
        "home_adv":        float(params[n]) if home_adv else 0.0,
        "log_likelihood":  float(-result.fun),
        "n_teams":         n,
    }


def win_probability(
    home_id: str, away_id: str, model: dict
) -> tuple[float, float]:
    """
    Return (p_home_win, p_away_win).  No draw term — use Elo for that.
    """
    s = model["teams"]
    s_h = s.get(home_id, 0.0)
    s_a = s.get(away_id, 0.0)
    p_home = float(expit(s_h - s_a + model.get("home_adv", 0.0)))
    return p_home, 1.0 - p_home


def ratings_df(model: dict, teams_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a tidy DataFrame of team strengths sorted descending."""
    rows = [
        {"team_id": tid, "bt_strength": strength}
        for tid, strength in model["teams"].items()
    ]
    df = pd.DataFrame(rows).sort_values("bt_strength", ascending=False).reset_index(drop=True)
    if teams_df is not None and not teams_df.empty:
        tmap = dict(zip(teams_df["id"], teams_df["name"]))
        df["team"] = df["team_id"].map(tmap).fillna(df["team_id"])
    return df
