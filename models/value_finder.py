"""
Value finder: surfaces model edges vs DraftKings lines.

Uses Elo model for match-winner markets and the try-scorer model
for player prop markets.
"""

import pandas as pd
import numpy as np
from utils.odds import american_to_implied, expected_value, format_american
from models.elo import win_probability, current_ratings


def _latest_odds(odds_df: pd.DataFrame) -> pd.DataFrame:
    """Return the most recently scraped odds row per match."""
    if odds_df.empty:
        return pd.DataFrame()
    return (
        odds_df.sort_values("scraped_at")
               .groupby("match_id")
               .last()
               .reset_index()
    )


def find_match_edges(
    upcoming: pd.DataFrame,
    odds_df: pd.DataFrame,
    elo_df: pd.DataFrame,
    min_edge: float = 0.05,
) -> pd.DataFrame:
    """
    Compare Elo win-probabilities against DraftKings moneylines.
    Returns rows where |model_prob − implied_prob| >= min_edge.
    """
    if upcoming.empty or odds_df.empty or elo_df.empty:
        return pd.DataFrame()

    ratings  = current_ratings(elo_df)
    lo       = _latest_odds(odds_df)
    records  = []

    for _, match in upcoming.iterrows():
        mid   = match["id"]
        row_o = lo[lo["match_id"] == mid]
        if row_o.empty:
            continue
        o = row_o.iloc[0]

        r_h   = ratings.get(match["home_team_id"], 1500)
        r_a   = ratings.get(match["away_team_id"], 1500)
        p_h, p_d, p_a = win_probability(r_h, r_a)

        for side, model_p, dk_ml, label in [
            ("home", p_h, o.get("home_ml"), "Home ML"),
            ("away", p_a, o.get("away_ml"), "Away ML"),
        ]:
            if pd.isna(dk_ml) or dk_ml == 0:
                continue
            dk_ml   = float(dk_ml)
            implied = american_to_implied(dk_ml)
            edge    = model_p - implied
            ev      = expected_value(model_p, dk_ml)

            if abs(edge) >= min_edge:
                records.append({
                    "match_id":       mid,
                    "home_team_id":   match["home_team_id"],
                    "away_team_id":   match["away_team_id"],
                    "league_id":      match.get("league_id", ""),
                    "kickoff_utc":    match.get("kickoff_utc"),
                    "market":         label,
                    "dk_odds":        format_american(dk_ml),
                    "dk_implied_pct": round(implied * 100, 1),
                    "model_pct":      round(model_p * 100, 1),
                    "edge_pct":       round(edge * 100, 1),
                    "ev":             round(ev, 3),
                    "direction":      "back" if edge > 0 else "fade",
                })

    return pd.DataFrame(records)


def find_try_scorer_edges(
    upcoming: pd.DataFrame,
    player_stats: pd.DataFrame,
    try_scorer_model,
    dk_try_scorer_odds: pd.DataFrame | None = None,
    min_edge: float = 0.05,
) -> pd.DataFrame:
    """
    Compare model try-scorer probabilities vs DraftKings anytime try-scorer lines.
    dk_try_scorer_odds should have columns: player_id, match_id, dk_odds (American).
    If not provided, just returns model probabilities for context.
    """
    from models.try_scorer import top_try_scorers_for_match

    if upcoming.empty or try_scorer_model is None:
        return pd.DataFrame()

    records = []
    for _, match in upcoming.iterrows():
        scored_df = top_try_scorers_for_match(
            match["home_team_id"], match["away_team_id"],
            player_stats, try_scorer_model, n=10,
        )
        if scored_df.empty:
            continue

        for _, p in scored_df.iterrows():
            model_p = p["prob"]
            rec = {
                "match_id":    match["id"],
                "player_name": p["player_name"],
                "team_id":     p["team_id"],
                "model_pct":   round(model_p * 100, 1),
                "model_odds":  format_american(
                    -(model_p / (1 - model_p) * 100) if model_p > 0.5
                    else (1 - model_p) / model_p * 100
                ),
            }
            # Attach DK odds if available
            if dk_try_scorer_odds is not None and not dk_try_scorer_odds.empty:
                row_dk = dk_try_scorer_odds[
                    (dk_try_scorer_odds["player_id"] == p["player_id"]) &
                    (dk_try_scorer_odds["match_id"]  == match["id"])
                ]
                if not row_dk.empty:
                    dk_ml   = float(row_dk.iloc[0]["dk_odds"])
                    implied = american_to_implied(dk_ml)
                    edge    = model_p - implied
                    if abs(edge) >= min_edge:
                        rec["dk_odds"]        = format_american(dk_ml)
                        rec["dk_implied_pct"] = round(implied * 100, 1)
                        rec["edge_pct"]       = round(edge * 100, 1)
                        rec["ev"]             = round(expected_value(model_p, dk_ml), 3)
            records.append(rec)

    return pd.DataFrame(records)


def form_score(results: list, weights: list = None) -> float:
    """
    Weighted form score 0–100. results = ['W','D','L',...] most recent first.
    """
    if weights is None:
        weights = [1.0, 0.8, 0.6, 0.4, 0.2]
    numeric = {"W": 1.0, "D": 0.5, "L": 0.0}
    vals = [numeric.get(r, 0) for r in results[:5]]
    w    = weights[:len(vals)]
    if not w:
        return 0.0
    return round((sum(v * wt for v, wt in zip(vals, w)) / sum(w)) * 100, 1)
