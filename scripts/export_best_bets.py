"""
scripts/export_best_bets.py — Rugby (rugby)
Runs the Value Finder in-memory against today's scheduled matches and writes
data_files/best_bets_today.json in the unified Sports Picks Grid schema.
"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SPORT = "Rugby"
MODEL_VERSION = "1.0.0"
SEASON = str(date.today().year)
OUT_PATH = ROOT / "data_files" / "best_bets_today.json"


def _write(bets: list, notes: str = "") -> None:
    payload: dict = {
        "meta": {
            "sport": SPORT,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": MODEL_VERSION,
            "season": SEASON,
        },
        "bets": bets,
    }
    if notes:
        payload["meta"]["notes"] = notes
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"[{SPORT}] Wrote {len(bets)} bets -> {OUT_PATH}")


def _tier_from_edge(edge: float) -> str:
    if edge >= 0.10:
        return "Elite"
    elif edge >= 0.05:
        return "Strong"
    elif edge >= 0.02:
        return "Good"
    return "Standard"


MARKET_MAP = {"ML": "Match Winner", "Moneyline": "Match Winner"}


def main() -> None:
    today = date.today()

    try:
        import pandas as pd
        from utils.cache import load_matches, load_teams, load_leagues, load_odds
        from models.elo import build_elo_history
        from models.value_finder import find_match_edges
    except ImportError as e:
        _write([], f"Import error: {e}")
        return

    try:
        matches_df = load_matches()
        teams_df   = load_teams()
        leagues_df = load_leagues()
        odds_df    = load_odds()
    except Exception as e:
        _write([], f"Failed to load data: {e}")
        return

    if matches_df.empty:
        _write([], "No match data available")
        return

    # Filter upcoming matches for today
    if "kickoff_utc" in matches_df.columns:
        matches_df["kickoff_utc"] = pd.to_datetime(matches_df["kickoff_utc"], utc=True, errors="coerce")
        today_matches = matches_df[
            (matches_df["status"] == "scheduled") &
            (matches_df["kickoff_utc"].dt.date == today)
        ]
    else:
        today_matches = matches_df[matches_df.get("status", pd.Series()) == "scheduled"]

    if today_matches.empty:
        _write([], f"No scheduled rugby matches for {today}")
        return

    # Build team lookup
    if "id" in teams_df.columns and "name" in teams_df.columns:
        tname = dict(zip(teams_df["id"], teams_df["name"]))
    else:
        tname = {}

    if "id" in leagues_df.columns and "name" in leagues_df.columns:
        lname = dict(zip(leagues_df["id"], leagues_df["name"]))
    else:
        lname = {}

    try:
        elo_df = build_elo_history(matches_df)
        edges  = find_match_edges(today_matches, odds_df, elo_df, min_edge=0.02)
    except Exception as e:
        _write([], f"Value finder failed: {e}")
        return

    if edges.empty:
        _write([], f"No Rugby value edges for {today}")
        return

    bets = []
    for _, row in edges.iterrows():
        home_id = row.get("home_team_id")
        away_id = row.get("away_team_id")
        home    = tname.get(home_id, str(home_id))
        away    = tname.get(away_id, str(away_id))
        league  = lname.get(row.get("league_id"), "")
        edge    = float(row.get("edge_pct", row.get("edge", 0)))
        conf    = float(row.get("model_pct", row.get("model_prob", 0.5)))
        market  = MARKET_MAP.get(str(row.get("market", "")), str(row.get("market", "Match Winner")))
        direction = str(row.get("direction", "back"))
        pick   = f"{'Back' if direction == 'back' else 'Fade'} {home if direction == 'back' else away}"
        odds   = row.get("dk_odds")

        # Kickoff time
        ko = row.get("kickoff_utc")
        game_time = str(ko).split("T")[-1][:5] if ko and str(ko) not in ("nan", "None") else None

        bet: dict = {
            "game_date": str(today),
            "game_time": game_time,
            "game": f"{away} @ {home}",
            "home_team": home,
            "away_team": away,
            "bet_type": market,
            "pick": pick,
            "confidence": round(conf, 4),
            "edge": round(edge, 4),
            "tier": _tier_from_edge(edge),
            "odds": int(odds) if odds and str(odds) not in ("nan", "None") else None,
            "line": None,
            "league": league,
        }
        bets.append(bet)

    _write(bets, "" if bets else f"No qualifying Rugby picks for {today}")


if __name__ == "__main__":
    main()
