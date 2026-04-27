"""Odds format conversion and expected-value helpers."""


def american_to_implied(american_odds: float) -> float:
    """Convert American odds to implied probability (vig NOT removed)."""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    return abs(american_odds) / (abs(american_odds) + 100)


def implied_to_american(prob: float) -> int:
    """Convert implied probability to American odds (nearest integer)."""
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return -round(prob / (1 - prob) * 100)
    return round((1 - prob) / prob * 100)


def decimal_to_american(decimal_odds: float) -> int:
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1) * 100)
    return round(-100 / (decimal_odds - 1))


def american_to_decimal(american_odds: float) -> float:
    if american_odds > 0:
        return (american_odds / 100) + 1
    return (100 / abs(american_odds)) + 1


def no_vig_probs(home_ml: float, away_ml: float) -> tuple[float, float]:
    """Remove bookmaker margin and return true win probabilities."""
    h = american_to_implied(home_ml)
    a = american_to_implied(away_ml)
    total = h + a
    return h / total, a / total


def expected_value(model_prob: float, american_odds: float) -> float:
    """
    Expected value per $1 risked.
    Positive EV = +edge over bookmaker.
    """
    if american_odds > 0:
        profit_if_win = american_odds / 100
    else:
        profit_if_win = 100 / abs(american_odds)
    return (model_prob * profit_if_win) - ((1 - model_prob) * 1)


def has_edge(model_prob: float, american_odds: float, min_edge: float = 0.05) -> bool:
    implied = american_to_implied(american_odds)
    return (model_prob - implied) >= min_edge


def format_american(odds: float) -> str:
    if odds is None:
        return "—"
    return f"{int(odds):+d}"
