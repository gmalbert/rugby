"""
Monte Carlo season and knockout bracket simulation for ScrumBet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from models.elo import win_probability, current_ratings


# ── Season simulation ──────────────────────────────────────────────────────

def simulate_season(
    remaining_fixtures: pd.DataFrame,
    elo_df: pd.DataFrame,
    current_table: pd.DataFrame,
    n_sims: int = 10_000,
) -> pd.DataFrame:
    """
    Simulate remaining fixtures n_sims times using Elo win probabilities.

    Parameters
    ----------
    remaining_fixtures:
        Scheduled matches (status == "scheduled") with home_team_id / away_team_id.
    elo_df:
        Elo ratings parquet (from load_elo_ratings).
    current_table:
        Current standings with team_id and league_points columns.
    n_sims:
        Number of Monte Carlo iterations.

    Returns
    -------
    DataFrame indexed by team_id with per-position finish probabilities,
    plus ``winner_prob`` and ``top4_prob`` summary columns.
    """
    if remaining_fixtures.empty:
        return pd.DataFrame()

    ratings = current_ratings(elo_df).to_dict() if not elo_df.empty else {}
    teams = sorted(
        set(remaining_fixtures["home_team_id"]) | set(remaining_fixtures["away_team_id"])
    )
    n_teams = len(teams)
    if n_teams == 0:
        return pd.DataFrame()

    tidx = {t: i for i, t in enumerate(teams)}

    base_pts: dict[str, float] = {}
    if not current_table.empty and "team_id" in current_table.columns:
        col = "league_points" if "league_points" in current_table.columns else current_table.columns[-1]
        base_pts = dict(zip(current_table["team_id"], current_table[col]))

    finish_counts = np.zeros((n_teams, n_teams), dtype=np.int32)
    rng = np.random.default_rng(42)

    for _ in range(n_sims):
        pts = {t: float(base_pts.get(t, 0)) for t in teams}
        for _, f in remaining_fixtures.iterrows():
            h = f["home_team_id"]
            a = f["away_team_id"]
            ph, _, pa = win_probability(ratings.get(h, 1500), ratings.get(a, 1500))
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
        columns=[f"P{i + 1}" for i in range(n_teams)],
    )
    top_n = min(4, n_teams)
    result["top4_prob"] = result[[f"P{i + 1}" for i in range(top_n)]].sum(axis=1)
    result["winner_prob"] = result["P1"]
    result.index.name = "team_id"
    return result.reset_index().sort_values("winner_prob", ascending=False).reset_index(drop=True)


# ── Knockout bracket simulation ────────────────────────────────────────────

def simulate_ko_bracket(
    seeds: list[str],
    ratings: dict[str, float],
    n: int = 10_000,
) -> pd.DataFrame:
    """
    Simulate a single-elimination knockout bracket n times.

    Parameters
    ----------
    seeds:
        Ordered list of team IDs.  Matchups: 1v2, 3v4, 5v6 … (sequential pairs).
    ratings:
        Dict of team_id → Elo rating.
    n:
        Number of simulations.

    Returns
    -------
    DataFrame with team_id and title_prob columns, sorted descending.
    """
    assert len(seeds) in (2, 4, 8, 16), "Bracket must be 2, 4, 8, or 16 teams"
    win_counts: dict[str, int] = {t: 0 for t in seeds}
    rng = np.random.default_rng(42)

    for _ in range(n):
        bracket = list(seeds)
        while len(bracket) > 1:
            next_round: list[str] = []
            for i in range(0, len(bracket), 2):
                h, a = bracket[i], bracket[i + 1]
                ph, _, _ = win_probability(ratings.get(h, 1500), ratings.get(a, 1500))
                winner = h if rng.random() < ph else a
                next_round.append(winner)
            bracket = next_round
        win_counts[bracket[0]] += 1

    return (
        pd.DataFrame(
            [{"team_id": t, "title_prob": win_counts[t] / n} for t in seeds]
        )
        .sort_values("title_prob", ascending=False)
        .reset_index(drop=True)
    )


def simulate_ko_bracket_rounds(
    seeds: list[str],
    ratings: dict[str, float],
    n: int = 10_000,
) -> pd.DataFrame:
    """
    Like simulate_ko_bracket but tracks progression probability per round.
    Returns a DataFrame with Team + one column per round (QF / SF / Final / Winner).
    """
    n_teams = len(seeds)
    assert n_teams in (2, 4, 8, 16)
    n_rounds = int(np.log2(n_teams))

    round_labels = ["R1 Win", "QF Win", "SF Win", "Final Win", "Champion"]
    labels = round_labels[-n_rounds:]  # trim to actual rounds

    advance_counts: dict[str, list[int]] = {t: [0] * n_rounds for t in seeds}
    rng = np.random.default_rng(42)

    for _ in range(n):
        bracket = list(seeds)
        round_idx = 0
        while len(bracket) > 1:
            next_round: list[str] = []
            for i in range(0, len(bracket), 2):
                h, a = bracket[i], bracket[i + 1]
                ph, _, _ = win_probability(ratings.get(h, 1500), ratings.get(a, 1500))
                winner = h if rng.random() < ph else a
                advance_counts[winner][round_idx] += 1
                next_round.append(winner)
            bracket = next_round
            round_idx += 1

    rows = []
    for t in seeds:
        row: dict = {"team_id": t}
        for i, lbl in enumerate(labels):
            row[lbl] = f"{advance_counts[t][i] / n:.1%}"
        rows.append(row)

    return pd.DataFrame(rows)
