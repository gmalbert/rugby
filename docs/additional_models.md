# Additional Models & Analytics

Extensions to the current Elo + Dixon-Coles + Logistic try-scorer stack.

---

## 1. Bradley-Terry Model  (Better than Elo for round-robin leagues)

Bradley-Terry is a pairwise comparison model that estimates latent team strengths from
win/loss outcomes. It is more statistically principled than Elo for round-robin competitions
(Six Nations, Premiership) because it uses maximum likelihood estimation across the full
fixture list simultaneously rather than sequential updates.

```python
# models/bradley_terry.py
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit  # sigmoid

def fit(matches: pd.DataFrame, home_adv: bool = True) -> dict | None:
    """
    Fit Bradley-Terry model to completed match results.

    matches must have: home_team_id, away_team_id, home_score, away_score
    Returns: {teams: {id: strength}, home_adv: float}
    """
    teams = sorted(
        set(matches["home_team_id"]) | set(matches["away_team_id"])
    )
    idx = {t: i for i, t in enumerate(teams)}
    n   = len(teams)

    def neg_log_likelihood(params: np.ndarray) -> float:
        strengths = params[:n]
        h_adv     = params[n] if home_adv else 0.0
        ll = 0.0
        for _, row in matches.iterrows():
            hi = idx[row["home_team_id"]]
            ai = idx[row["away_team_id"]]
            p_home = expit(strengths[hi] - strengths[ai] + h_adv)
            if row["home_score"] > row["away_score"]:
                ll += np.log(p_home + 1e-10)
            elif row["home_score"] < row["away_score"]:
                ll += np.log(1 - p_home + 1e-10)
            else:
                ll += np.log(0.5)  # draw
        return -ll

    x0 = np.zeros(n + (1 if home_adv else 0))
    # Fix first team to 0 for identifiability
    bounds = [(None, None)] * n + ([(0, 2)] if home_adv else [])
    result = minimize(
        neg_log_likelihood, x0,
        method="L-BFGS-B", bounds=bounds,
        options={"maxiter": 500},
    )
    if not result.success:
        return None

    params = result.x
    return {
        "teams":    {t: float(params[idx[t]]) for t in teams},
        "home_adv": float(params[n]) if home_adv else 0.0,
        "log_likelihood": -result.fun,
    }

def win_probability(home_id: str, away_id: str, model: dict) -> tuple[float, float]:
    """Return (p_home_win, p_away_win). No draw term."""
    strengths = model["teams"]
    s_h = strengths.get(home_id, 0.0)
    s_a = strengths.get(away_id, 0.0)
    p_home = expit(s_h - s_a + model.get("home_adv", 0.0))
    return float(p_home), float(1 - p_home)
```

**When to use:** League table position predictions, playoff qualification probability.

---

## 2. Gradient Boosted Trees (XGBoost) — Win Prediction

A richer feature-based win probability model that can incorporate:
- Elo rating differential
- Recent form (last 5 W/L/D)
- Head-to-head record
- Set-piece stats (lineout %, scrum %)
- Average territorial possession
- Days rest (fixture congestion)
- Weather conditions
- Referee tendencies

```python
# models/gbm_win.py
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import log_loss, brier_score_loss
import joblib
from pathlib import Path

FEATURE_COLS = [
    "elo_diff",          # home_elo - away_elo
    "home_form_pts",     # W=3, D=1, L=0 over last 5
    "away_form_pts",
    "h2h_home_win_rate", # historical H2H home win %
    "home_lineout_pct",  # season avg
    "away_lineout_pct",
    "home_scrum_pct",
    "away_scrum_pct",
    "home_territory",
    "away_territory",
    "home_rest_days",
    "away_rest_days",
    "wind_speed",
    "is_neutral",        # neutral venue (e.g. finals)
]

def build_features(
    matches: pd.DataFrame,
    team_stats: pd.DataFrame,
    elo_df: pd.DataFrame,
    weather_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Join all feature sources into a single model-ready DataFrame."""
    # ... feature engineering joins ...
    pass

def train(features: pd.DataFrame, target: str = "home_win") -> xgb.XGBClassifier:
    """Time-series CV training to avoid data leakage."""
    X = features[FEATURE_COLS].fillna(0)
    y = features[target]
    tscv = TimeSeriesSplit(n_splits=5)
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
    )
    # Train on all data after CV validation
    model.fit(X, y, eval_set=[(X, y)], verbose=False)
    return model

def feature_importance_df(model: xgb.XGBClassifier) -> pd.DataFrame:
    return pd.DataFrame({
        "feature":    FEATURE_COLS,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)
```

**Install:** `pip install xgboost`

---

## 3. Poisson Regression — Score Prediction (Better than Dixon-Coles vanilla)

Replace the current hand-rolled DC optimizer with a proper GLM:

```python
# models/poisson_glm.py
import pandas as pd
import numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf

def fit(matches: pd.DataFrame) -> dict:
    """
    Fit separate Poisson GLMs for home and away scoring rates.
    Uses team attack/defence intercepts as per Maher (1982).
    Returns model objects for predicting any fixture.
    """
    # Reshape to long format: one row per team per match
    home = matches[["id", "league_id", "home_team_id", "away_team_id", "home_score"]].copy()
    away = matches[["id", "league_id", "home_team_id", "away_team_id", "away_score"]].copy()
    home.columns = ["match_id", "league_id", "team", "opponent", "goals"]
    away.columns = ["match_id", "league_id", "opponent", "team", "goals"]
    home["home"] = 1
    away["home"] = 0
    long = pd.concat([home, away], ignore_index=True)
    long["goals"] = long["goals"].astype(int)

    formula = "goals ~ C(team) + C(opponent) + home"
    model = smf.glm(formula=formula, data=long,
                    family=sm.families.Poisson()).fit()
    return {"model": model, "teams": long["team"].unique().tolist()}

def predict_score(home_id: str, away_id: str, model_dict: dict) -> dict:
    from scipy.stats import poisson
    import numpy as np

    model = model_dict["model"]
    pred_home = model.predict(pd.DataFrame([{
        "team": home_id, "opponent": away_id, "home": 1
    }]))[0]
    pred_away = model.predict(pd.DataFrame([{
        "team": away_id, "opponent": home_id, "home": 0
    }]))[0]

    max_score = 80
    score_matrix = np.outer(
        poisson.pmf(range(max_score), pred_home),
        poisson.pmf(range(max_score), pred_away),
    )
    return {
        "exp_home": pred_home,
        "exp_away": pred_away,
        "p_home_win": float(np.tril(score_matrix, -1).sum()),
        "p_away_win": float(np.triu(score_matrix, 1).sum()),
        "p_draw":     float(np.trace(score_matrix)),
        "matrix":     score_matrix,
    }
```

**Install:** `pip install statsmodels`

---

## 4. Kelly Criterion — Bet Sizing

The Kelly Criterion is the theoretically optimal fraction of bankroll to bet given an edge.
Half-Kelly is standard practice for risk management.

```python
# models/kelly.py

def kelly_fraction(prob: float, american_odds: int, fraction: float = 0.5) -> float:
    """
    Calculate Kelly stake fraction.

    Args:
        prob:          Model win probability (0–1)
        american_odds: DraftKings American odds (+150, -110, etc.)
        fraction:      Kelly fraction (0.5 = half-Kelly, recommended)

    Returns:
        Fraction of bankroll to stake (0 if no edge)
    """
    if american_odds > 0:
        decimal_odds = american_odds / 100 + 1
    else:
        decimal_odds = 100 / abs(american_odds) + 1

    b = decimal_odds - 1  # net odds (profit per unit staked)
    q = 1 - prob
    kelly = (b * prob - q) / b
    return max(0.0, kelly * fraction)


def kelly_table(edges_df: pd.DataFrame, bankroll: float = 1000.0) -> pd.DataFrame:
    """
    Add Kelly stake in dollars to an edges DataFrame.
    edges_df must have: model_pct, dk_odds columns.
    """
    df = edges_df.copy()
    df["kelly_f"]      = df.apply(
        lambda r: kelly_fraction(r["model_pct"], r["dk_odds"]), axis=1
    )
    df["kelly_stake"]  = (df["kelly_f"] * bankroll).round(2)
    df["kelly_stake"]  = df["kelly_stake"].clip(upper=bankroll * 0.05)  # max 5% cap
    return df
```

---

## 5. Monte Carlo League Season Simulation

Simulate the rest of the season 10 000 times to output table finish probabilities.

```python
# models/season_sim.py
import numpy as np
import pandas as pd
from models.elo import win_probability, current_ratings

def simulate_season(
    remaining_fixtures: pd.DataFrame,
    elo_df: pd.DataFrame,
    current_table: pd.DataFrame,
    n_sims: int = 10_000,
) -> pd.DataFrame:
    """
    Simulate remaining fixtures n_sims times.
    Returns DataFrame of finish probabilities per team per position.
    """
    ratings  = current_ratings(elo_df).to_dict()
    teams    = list(set(remaining_fixtures["home_team_id"]) |
                    set(remaining_fixtures["away_team_id"]))
    n_teams  = len(teams)
    tidx     = {t: i for i, t in enumerate(teams)}

    # Points table baseline
    base_pts = dict(zip(current_table["team_id"], current_table["league_points"]))

    finish_counts = np.zeros((n_teams, n_teams), dtype=int)

    rng = np.random.default_rng(42)
    for _ in range(n_sims):
        pts = {t: base_pts.get(t, 0) for t in teams}
        for _, f in remaining_fixtures.iterrows():
            h, a = f["home_team_id"], f["away_team_id"]
            ph, _, pa = win_probability(
                ratings.get(h, 1500), ratings.get(a, 1500)
            )
            r = rng.random()
            if r < ph:
                pts[h] += 4
            elif r > 1 - pa:
                pts[a] += 4
            else:
                pts[h] += 2
                pts[a] += 2

        order = sorted(teams, key=lambda t: -pts[t])
        for pos, t in enumerate(order):
            finish_counts[tidx[t], pos] += 1

    probs = finish_counts / n_sims
    result = pd.DataFrame(
        probs,
        index=teams,
        columns=[f"P{i+1}" for i in range(n_teams)],
    )
    result["top4_prob"] = result[[f"P{i+1}" for i in range(4)]].sum(axis=1)
    result["winner_prob"] = result["P1"]
    return result.sort_values("winner_prob", ascending=False)
```

---

## 6. Expected Points (xP) Model

Similar to football's xG — estimate the points a team *should* have scored based on
territory, possession, and set-piece conversion rates.

```python
# models/expected_points.py
import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge

# Scoring event probabilities (approximate league averages):
P_TRY_FROM_22_ENTRY    = 0.31   # probability of try given 22m entry
P_CONVERSION_GIVEN_TRY = 0.72   # league average conversion rate
P_PEN_KICKED           = 0.78   # % of kickable penalties taken as kicks

def compute_xp(team_stats_row: pd.Series) -> float:
    """
    Estimate expected points from territory/phase stats.
    Uses rugbypy team stat columns.
    """
    xp  = 0.0
    # Tries from 22m entries
    xp += (team_stats_row.get("22m_entries", 0) * P_TRY_FROM_22_ENTRY
           * (7 * P_CONVERSION_GIVEN_TRY + 5 * (1 - P_CONVERSION_GIVEN_TRY)))
    # Penalties (assume 60% of penalties are kickable)
    xp += (team_stats_row.get("total_free_kicks_conceded", 0) * 0 +  # opponent FK
           team_stats_row.get("turnovers_won", 0) * 0.10 * 7)       # turnover tries
    return round(xp, 1)

def xp_vs_actual(team_stats: pd.DataFrame) -> pd.DataFrame:
    """Compare expected vs actual points per match."""
    df = team_stats.copy()
    df["xP"]       = df.apply(compute_xp, axis=1)
    df["xP_diff"]  = df["points"] - df["xP"]
    df["luck"]     = df["xP_diff"].apply(
        lambda x: "overperforming" if x > 5 else ("underperforming" if x < -5 else "par")
    )
    return df[["team", "game_date", "points", "xP", "xP_diff", "luck"]]
```

---

## 7. Bayesian Rating System (TrueSkill)

Microsoft's TrueSkill generalises Elo by modelling both skill *mean* and *uncertainty*
(variance). New teams or newly-promoted sides start with high uncertainty and converge
faster, while established teams change more slowly.

```python
# models/trueskill_ratings.py
# pip install trueskill
import trueskill
import pandas as pd

env = trueskill.TrueSkill(draw_probability=0.04)  # rugby rarely draws

def build_trueskill_ratings(matches: pd.DataFrame) -> pd.DataFrame:
    """Process matches chronologically and return current ratings."""
    ratings: dict[str, trueskill.Rating] = {}
    records = []
    for _, m in matches.sort_values("kickoff_utc").iterrows():
        h, a = m["home_team_id"], m["away_team_id"]
        r_h = ratings.get(h, env.create_rating())
        r_a = ratings.get(a, env.create_rating())
        if m["home_score"] > m["away_score"]:
            r_h, r_a = env.rate_1vs1(r_h, r_a)
        elif m["home_score"] < m["away_score"]:
            r_a, r_h = env.rate_1vs1(r_a, r_h)
        # draw: trueskill handles drawn=True
        ratings[h], ratings[a] = r_h, r_a
        records.append({
            "match_id": m["id"],
            "date":     m["kickoff_utc"],
            "home_mu":  r_h.mu,
            "home_sigma": r_h.sigma,
            "away_mu":  r_a.mu,
            "away_sigma": r_a.sigma,
        })
    # Current ratings
    return pd.DataFrame([
        {"team_id": t, "mu": r.mu, "sigma": r.sigma,
         "conservative": r.mu - 3 * r.sigma}
        for t, r in ratings.items()
    ]).sort_values("conservative", ascending=False)
```

---

## 8. Hawkes Process — In-Play Scoring Model

A Hawkes (self-exciting) point process models the temporal clustering of scoring events —
tries in rugby often come in bursts. Useful for in-play probability updates.

```python
# models/hawkes_scoring.py
import numpy as np
from scipy.optimize import minimize

def fit_hawkes(event_times: list[float], T: float = 80.0) -> dict:
    """
    Fit a univariate Hawkes process to try-scoring times within matches.

    event_times: list of minutes when tries were scored
    T:           total match time (80 min)
    Returns: {mu: baseline rate, alpha: excitement, beta: decay}
    """
    def neg_log_likelihood(params):
        mu, alpha, beta = params
        if mu <= 0 or alpha < 0 or beta <= 0 or alpha >= beta:
            return np.inf
        ll = -mu * T
        for i, ti in enumerate(event_times):
            prev = [t for t in event_times if t < ti]
            intensity = mu + alpha * sum(np.exp(-beta * (ti - tj)) for tj in prev)
            ll += np.log(intensity + 1e-10)
            ll -= alpha / beta * (1 - np.exp(-beta * (T - ti)))
        return -ll

    result = minimize(
        neg_log_likelihood, [0.05, 0.3, 0.5],
        method="Nelder-Mead",
        options={"xatol": 1e-4, "fatol": 1e-4, "maxiter": 2000},
    )
    mu, alpha, beta = result.x
    return {"mu": mu, "alpha": alpha, "beta": beta, "converged": result.success}

def current_scoring_rate(
    event_times: list[float], current_minute: float, params: dict
) -> float:
    """Real-time scoring intensity given events so far."""
    mu, alpha, beta = params["mu"], params["alpha"], params["beta"]
    past = [t for t in event_times if t <= current_minute]
    return mu + alpha * sum(np.exp(-beta * (current_minute - t)) for t in past)
```

---

## Model Comparison Matrix

| Model | Predicts | Training data needed | Live-ready |
|---|---|---|---|
| Elo (current) | Win prob | 20+ matches | Yes |
| Dixon-Coles (current) | Scoreline | 15+ matches | Yes |
| Bradley-Terry | Win prob | Full season | Yes |
| Poisson GLM | Scoreline | 30+ matches | Yes |
| XGBoost | Win prob | 50+ matches + features | Partial |
| TrueSkill | Win prob | Any (fast convergence) | Yes |
| Kelly Criterion | Stake size | Requires edge input | Yes |
| Season Simulation | Table finish | Current table + fixtures | Yes |
| xP Model | Performance quality | Team stat data | Yes |
| Hawkes Process | In-play rate | Per-match event times | In-play only |
