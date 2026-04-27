"""
Dixon-Coles score-prediction model for rugby.

Fits per-team attack / defence parameters via maximum likelihood on
historical final scores. Outputs a full scoreline probability matrix,
win/draw/loss probabilities, and expected totals.

Note: rugby scoring comes in 3s, 5s, and 7s so Poisson is an approximation.
The model is nevertheless predictive and widely used in sports analytics.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson


# ── Dixon-Coles low-score correction ──────────────────────────────────────

def _tau(x: int, y: int, mu_h: float, mu_a: float, rho: float) -> float:
    """Correction factor for low (0–1) scoreline combinations."""
    if x == 0 and y == 0:
        return 1 - mu_h * mu_a * rho
    if x == 0 and y == 1:
        return 1 + mu_h * rho
    if x == 1 and y == 0:
        return 1 + mu_a * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


# ── Model fitting ──────────────────────────────────────────────────────────

def fit(matches: pd.DataFrame) -> dict | None:
    """
    Fit the Dixon-Coles model on a DataFrame of completed matches.

    Returns a dict:
      {
        "teams":    {team_id: {"attack": float, "defence": float}},
        "home_adv": float,
        "rho":      float,
      }
    or None if there is insufficient data.
    """
    df = matches[matches["status"] == "final"].dropna(
        subset=["home_score", "away_score"]
    ).copy()

    if len(df) < 15:
        return None

    teams = pd.unique(df[["home_team_id", "away_team_id"]].values.ravel())
    n     = len(teams)
    idx   = {t: i for i, t in enumerate(teams)}

    def neg_ll(params: np.ndarray) -> float:
        home_adv = params[0]
        rho      = params[1]
        attacks  = params[2:2 + n]
        defences = params[2 + n:]
        total = 0.0
        for _, row in df.iterrows():
            h  = idx[row["home_team_id"]]
            a  = idx[row["away_team_id"]]
            mu_h = np.exp(attacks[h] - defences[a] + home_adv)
            mu_a = np.exp(attacks[a] - defences[h])
            sh   = int(row["home_score"])
            sa   = int(row["away_score"])
            t    = _tau(sh, sa, mu_h, mu_a, rho)
            ll   = (
                np.log(max(t, 1e-10))
                + poisson.logpmf(sh, max(mu_h, 1e-6))
                + poisson.logpmf(sa, max(mu_a, 1e-6))
            )
            total += ll
        return -total

    x0  = np.zeros(2 + 2 * n)
    x0[0] = 0.15   # home_adv
    x0[1] = -0.10  # rho

    res = minimize(
        neg_ll, x0, method="L-BFGS-B",
        options={"maxiter": 300, "ftol": 1e-7},
    )

    if not res.success:
        return None

    p = res.x
    return {
        "teams": {
            t: {"attack": p[2 + i], "defence": p[2 + n + i]}
            for i, t in enumerate(teams)
        },
        "home_adv": float(p[0]),
        "rho":      float(p[1]),
    }


# ── Prediction ─────────────────────────────────────────────────────────────

def predict(
    home_id: str,
    away_id: str,
    model: dict,
    max_score: int = 80,
) -> dict | None:
    """
    Predict outcome probabilities and expected scores for one match.

    Returns:
      {
        "matrix":      np.ndarray (max_score × max_score),
        "p_home":      float,
        "p_draw":      float,
        "p_away":      float,
        "exp_home":    float,
        "exp_away":    float,
        "top_scorelines": [(home_score, away_score, prob), ...]
      }
    or None.
    """
    if model is None:
        return None

    team_params = model["teams"]
    if home_id not in team_params or away_id not in team_params:
        return None

    hp = team_params[home_id]
    ap = team_params[away_id]
    rho = model["rho"]

    mu_h = np.exp(hp["attack"] - ap["defence"] + model["home_adv"])
    mu_a = np.exp(ap["attack"] - hp["defence"])

    matrix = np.outer(
        [poisson.pmf(i, mu_h) for i in range(max_score)],
        [poisson.pmf(j, mu_a) for j in range(max_score)],
    )

    # Apply DC correction for low scores
    for i in range(min(2, max_score)):
        for j in range(min(2, max_score)):
            matrix[i, j] *= _tau(i, j, mu_h, mu_a, rho)

    p_home = float(np.sum(np.tril(matrix, -1)))
    p_draw = float(np.trace(matrix))
    p_away = float(np.sum(np.triu(matrix, 1)))

    # Top-5 most-likely scorelines
    flat   = np.argsort(matrix.ravel())[::-1][:5]
    rows, cols = np.unravel_index(flat, matrix.shape)
    top    = [(int(r), int(c), float(matrix[r, c])) for r, c in zip(rows, cols)]

    return {
        "matrix":        matrix,
        "p_home":        p_home,
        "p_draw":        p_draw,
        "p_away":        p_away,
        "exp_home":      mu_h,
        "exp_away":      mu_a,
        "top_scorelines": top,
    }


# ── Parameter table helper ─────────────────────────────────────────────────

def params_df(model: dict, teams_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a tidy DataFrame of attack/defence ratings."""
    if model is None:
        return pd.DataFrame()
    rows = []
    for team_id, vals in model["teams"].items():
        name = team_id
        if teams_df is not None and not teams_df.empty:
            row = teams_df[teams_df["id"] == team_id]
            if not row.empty:
                name = row["name"].iloc[0]
        rows.append({
            "team_id":  team_id,
            "team":     name,
            "attack":   round(vals["attack"], 3),
            "defence":  round(vals["defence"], 3),
        })
    return pd.DataFrame(rows).sort_values("attack", ascending=False)
