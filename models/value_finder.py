"""
Value finder: surfaces model edges vs bookmaker lines.

Uses Elo model for match-winner (ML) markets and Dixon-Coles for
spread and totals markets.

Odds sources:
  - odds_snapshots.csv  (pipeline-written, matched to ESPN match IDs)
  - load_live_rugby_odds() DataFrame (real-time from odds-api.io)

Live odds are matched to upcoming matches by fuzzy team name + date.
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


# ── Live-odds helpers (odds-api.io) ───────────────────────────────────────

def _match_live_odds_row(
    home_tid: str,
    away_tid: str,
    kickoff_utc,
    live_odds_df: pd.DataFrame,
    teams_df: pd.DataFrame,
) -> "pd.Series | None":
    """
    Return the live-odds row that matches the given ESPN fixture.
    Matching uses normalised team name + date proximity (±1 day).
    Returns None if no match found.
    """
    if live_odds_df.empty:
        return None

    from utils.odds_api_io import names_match

    tmap = dict(zip(teams_df["id"].astype(str), teams_df["name"])) if not teams_df.empty else {}
    home_name = tmap.get(str(home_tid), str(home_tid))
    away_name = tmap.get(str(away_tid), str(away_tid))
    ko = pd.Timestamp(kickoff_utc)
    if pd.isna(ko):
        return None

    for _, row in live_odds_df.iterrows():
        row_ko = pd.Timestamp(row["kickoff_utc"])
        if pd.isna(row_ko):
            continue
        if abs((ko.normalize() - row_ko.normalize()).days) > 1:
            continue
        if (names_match(home_name, str(row["home_name"])) and
                names_match(away_name, str(row["away_name"]))):
            return row
    return None


def find_live_match_edges(
    upcoming: pd.DataFrame,
    live_odds_df: pd.DataFrame,
    elo_df: pd.DataFrame,
    teams_df: pd.DataFrame,
    min_edge: float = 0.05,
) -> pd.DataFrame:
    """
    Compare Elo win-probabilities against live moneyline odds from odds-api.io.

    Unlike find_match_edges() which requires pre-matched CSV odds, this uses
    the live odds DataFrame returned by load_live_rugby_odds() and does fuzzy
    team-name matching on the fly.

    Returns rows where |model_prob − implied_prob| >= min_edge.
    """
    if upcoming.empty or live_odds_df.empty or elo_df.empty:
        return pd.DataFrame()

    ratings = current_ratings(elo_df)
    records = []

    for _, match in upcoming.iterrows():
        live_row = _match_live_odds_row(
            match["home_team_id"], match["away_team_id"],
            match.get("kickoff_utc"), live_odds_df, teams_df,
        )
        if live_row is None:
            continue

        r_h = ratings.get(match["home_team_id"], 1500)
        r_a = ratings.get(match["away_team_id"], 1500)
        p_h, p_d, p_a = win_probability(r_h, r_a)

        for side, model_p, ml_col, label in [
            ("home", p_h, "home_ml", "Home ML"),
            ("away", p_a, "away_ml", "Away ML"),
        ]:
            ml = live_row.get(ml_col)
            if pd.isna(ml) or ml == 0:
                continue
            ml = float(ml)
            implied = american_to_implied(ml)
            edge    = model_p - implied
            ev      = expected_value(model_p, ml)

            if abs(edge) >= min_edge:
                records.append({
                    "match_id":       match["id"],
                    "home_team_id":   match["home_team_id"],
                    "away_team_id":   match["away_team_id"],
                    "league_id":      match.get("league_id", ""),
                    "kickoff_utc":    match.get("kickoff_utc"),
                    "market":         label,
                    "bookmaker":      live_row.get("bookmaker", ""),
                    "dk_odds":        format_american(ml),
                    "dk_implied_pct": round(implied * 100, 1),
                    "model_pct":      round(model_p * 100, 1),
                    "edge_pct":       round(edge * 100, 1),
                    "ev":             round(ev, 3),
                    "direction":      "back" if edge > 0 else "fade",
                    "source":         "odds-api-io",
                })

    return pd.DataFrame(records)


def find_live_spread_edges(
    upcoming: pd.DataFrame,
    live_odds_df: pd.DataFrame,
    dc_model: dict | None,
    teams_df: pd.DataFrame,
    min_edge: float = 0.05,
) -> pd.DataFrame:
    """
    Compare Dixon-Coles expected point-difference against the offered spread.

    The spread market from BetMGM BR lists every available handicap; we use
    the main line (closest to 0). We compare DC's expected margin against the
    main line and flag edge when |dc_margin − spread_line| > threshold.

    Edge threshold here is in points, not probability — we use a 3-point
    minimum difference by default (one penalty in rugby).
    """
    if upcoming.empty or live_odds_df.empty or dc_model is None:
        return pd.DataFrame()

    from models.dixon_coles import predict

    records = []
    for _, match in upcoming.iterrows():
        live_row = _match_live_odds_row(
            match["home_team_id"], match["away_team_id"],
            match.get("kickoff_utc"), live_odds_df, teams_df,
        )
        if live_row is None:
            continue

        sp_line = live_row.get("spread_home")
        sp_odds = live_row.get("spread_home_odds")
        if pd.isna(sp_line) or pd.isna(sp_odds):
            continue

        res = predict(match["home_team_id"], match["away_team_id"], dc_model)
        if not res:
            continue

        dc_margin = res["exp_home"] - res["exp_away"]
        # Positive sp_line means home is favoured by that many points
        # Edge: if dc_margin > spread_line + threshold, model expects home to cover
        book_margin = -float(sp_line)  # hdp is from home perspective (negative = home fav)
        point_edge  = dc_margin - book_margin

        if abs(point_edge) >= 3:
            sp_odds_f = float(sp_odds)
            implied   = american_to_implied(sp_odds_f)
            # Probability of covering based on point edge magnitude
            # Simple sigmoid: each point of edge ≈ 3% prob shift from 50%
            cover_prob = min(0.95, max(0.05, 0.5 + point_edge * 0.03))
            ev = expected_value(cover_prob, sp_odds_f)

            records.append({
                "match_id":       match["id"],
                "home_team_id":   match["home_team_id"],
                "away_team_id":   match["away_team_id"],
                "league_id":      match.get("league_id", ""),
                "kickoff_utc":    match.get("kickoff_utc"),
                "market":         f"Spread {format_american(-int(sp_line))} pts",
                "bookmaker":      live_row.get("bookmaker", "BetMGM BR"),
                "dk_odds":        format_american(sp_odds_f),
                "dk_implied_pct": round(implied * 100, 1),
                "dc_margin":      round(dc_margin, 1),
                "book_margin":    round(book_margin, 1),
                "point_edge":     round(point_edge, 1),
                "ev":             round(ev, 3),
                "direction":      "back_home" if point_edge > 0 else "back_away",
                "source":         "odds-api-io",
            })

    return pd.DataFrame(records)


def find_live_totals_edges(
    upcoming: pd.DataFrame,
    live_odds_df: pd.DataFrame,
    dc_model: dict | None,
    teams_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare Dixon-Coles expected total points against the live O/U line.

    Returns all upcoming matches that have live totals odds, with DC expected
    total and a signal (Over / Under / Push) based on the difference.
    No minimum edge filter — all available matches are returned for context.
    """
    if upcoming.empty or live_odds_df.empty:
        return pd.DataFrame()

    from models.dixon_coles import predict

    records = []
    for _, match in upcoming.iterrows():
        live_row = _match_live_odds_row(
            match["home_team_id"], match["away_team_id"],
            match.get("kickoff_utc"), live_odds_df, teams_df,
        )
        if live_row is None:
            continue

        total_line  = live_row.get("total_line")
        over_odds   = live_row.get("total_over_odds")
        under_odds  = live_row.get("total_under_odds")
        if pd.isna(total_line):
            continue

        exp_total = None
        if dc_model:
            res = predict(match["home_team_id"], match["away_team_id"], dc_model)
            if res:
                exp_total = round(res["exp_home"] + res["exp_away"], 1)

        signal = "—"
        if exp_total is not None:
            diff = exp_total - float(total_line)
            if diff > 3:
                signal = "✅ Over"
            elif diff < -3:
                signal = "🔴 Under"
            else:
                signal = "⚖️ Push"

        records.append({
            "match_id":       match["id"],
            "home_team_id":   match["home_team_id"],
            "away_team_id":   match["away_team_id"],
            "league_id":      match.get("league_id", ""),
            "kickoff_utc":    match.get("kickoff_utc"),
            "bookmaker":      live_row.get("bookmaker", "BetMGM BR"),
            "total_line":     float(total_line),
            "over_odds":      format_american(over_odds) if not pd.isna(over_odds) else "—",
            "under_odds":     format_american(under_odds) if not pd.isna(under_odds) else "—",
            "dc_exp_total":   exp_total if exp_total is not None else "—",
            "signal":         signal,
            "source":         "odds-api-io",
        })

    return pd.DataFrame(records)
