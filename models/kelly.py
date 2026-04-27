"""Kelly Criterion stake sizing for ScrumBet."""

import pandas as pd


def kelly_fraction(prob: float, american_odds: float, fraction: float = 0.5) -> float:
    """
    Half-Kelly stake fraction.

    Args:
        prob:          Model win probability (0–1).
        american_odds: DraftKings American odds (+150, -120, etc.).
        fraction:      Kelly multiplier; 0.5 = half-Kelly (default, recommended).

    Returns:
        Fraction of bankroll to stake.  0 when there is no positive edge.
    """
    if american_odds > 0:
        decimal = american_odds / 100 + 1
    else:
        decimal = 100 / abs(american_odds) + 1

    b = decimal - 1          # net profit per unit staked
    q = 1.0 - prob
    raw = (b * prob - q) / b if b > 0 else 0.0
    return max(0.0, raw * fraction)


def kelly_table(
    edges_df: pd.DataFrame,
    bankroll: float = 1000.0,
    fraction: float = 0.5,
) -> pd.DataFrame:
    """
    Append kelly_f (fraction) and kelly_stake ($) columns to an edges DataFrame.

    edges_df must have columns: model_pct (float 0–1), dk_odds (American).
    kelly_stake is capped at 5% of bankroll as a hard risk limit.
    """
    df = edges_df.copy()
    df["kelly_f"] = df.apply(
        lambda r: kelly_fraction(float(r["model_pct"]), float(r["dk_odds"]), fraction),
        axis=1,
    )
    df["kelly_stake"] = (
        (df["kelly_f"] * bankroll).round(2).clip(upper=bankroll * 0.05)
    )
    return df
