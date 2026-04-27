"""
Page 5 — Betting Edge
Value bets table, try scorer props, totals, parlay builder, historical tracking.
"""

import streamlit as st
import pandas as pd

from utils.cache import (
    load_teams, load_matches, load_player_stats,
    load_elo_ratings, load_odds,
    fit_dc_cached, fit_try_scorer_cached,
)
from utils.config import LEAGUES, ODDS_API_KEY
from utils.odds import american_to_implied, expected_value, format_american
from models.elo import current_ratings, win_probability
from models.value_finder import find_match_edges, find_try_scorer_edges
from models.kelly import kelly_table

st.title("⚡ Betting Edge")
st.caption("Model-identified value vs DraftKings lines — informational only.")

# ── Load data ──────────────────────────────────────────────────────────────
teams_df   = load_teams()
matches_df = load_matches()
player_df  = load_player_stats()
elo_df     = load_elo_ratings()
odds_df    = load_odds()

_tmap = dict(zip(teams_df["id"], teams_df["name"])) if not teams_df.empty else {}
def tname(tid: str) -> str:
    return _tmap.get(tid, tid.split("-", 1)[-1].replace("-", " ").title())

# ── Sidebar controls ───────────────────────────────────────────────────────
min_edge = st.sidebar.slider("Min Edge %", min_value=1, max_value=20, value=5) / 100
bankroll    = st.sidebar.number_input("Bankroll ($)", min_value=10, max_value=100_000, value=1_000, step=50)
kelly_frac  = st.sidebar.select_slider(
    "Kelly fraction",
    options=[0.25, 0.5, 1.0],
    value=0.5,
    format_func=lambda x: {0.25: "¼ Kelly", 0.5: "½ Kelly", 1.0: "Full Kelly"}[x],
)
league_filter = st.sidebar.multiselect(
    "Leagues",
    options=list(LEAGUES.keys()),
    default=list(LEAGUES.keys()),
    format_func=lambda x: LEAGUES[x],
)

if matches_df.empty:
    st.info("No data loaded yet. Run `python scripts/pipeline.py` to populate.")
    st.stop()

# ── Upcoming fixtures ──────────────────────────────────────────────────────
from datetime import datetime, timezone, timedelta
now = datetime.now(timezone.utc)

upcoming = matches_df[
    (matches_df["kickoff_utc"] >= now) &
    (matches_df["kickoff_utc"] <= now + timedelta(days=14)) &
    (matches_df["status"] == "scheduled")
].copy()

if league_filter:
    upcoming = upcoming[upcoming["league_id"].isin(league_filter)]

# ── Value Bets Table ───────────────────────────────────────────────────────
st.subheader("💎 Value Bets — Match Winner")
st.caption(f"Showing edges ≥ {min_edge:.0%} between Elo model probability and DK implied probability.")

if upcoming.empty or odds_df.empty or elo_df.empty:
    if odds_df.empty and ODDS_API_KEY:
        st.info(
            "No odds data available. The Odds API only covers Six Nations (when active). "
            "Value bets will appear during the Six Nations tournament."
        )
    else:
        st.info("Value bets will appear here once match data, odds, and Elo ratings are available.")
else:
    edges_df = find_match_edges(upcoming, odds_df, elo_df, min_edge=min_edge)

    if edges_df.empty:
        st.info(f"No edges ≥ {min_edge:.0%} found in upcoming fixtures. Try lowering the threshold.")
    else:
        edges_df["Home"] = edges_df["home_team_id"].apply(tname)
        edges_df["Away"] = edges_df["away_team_id"].apply(tname)
        edges_df["Match"] = edges_df["Home"] + " vs " + edges_df["Away"]
        edges_df["League"] = edges_df["league_id"].map(LEAGUES).fillna(edges_df["league_id"])

        def highlight_edge(row):
            color = "#14532d" if row["direction"] == "back" else "#7f1d1d"
            return [f"background-color: {color}"] * len(row)

        disp = edges_df[[
            "Match", "League", "market", "dk_odds", "dk_implied_pct",
            "model_pct", "edge_pct", "ev", "direction",
        ]].rename(columns={
            "market": "Market", "dk_odds": "DK Odds",
            "dk_implied_pct": "DK Impl %", "model_pct": "Model %",
            "edge_pct": "Edge %", "ev": "EV ($1)", "direction": "Signal",
        })
        disp["Signal"] = disp["Signal"].map({"back": "✅ Back", "fade": "🔴 Fade"})

        # Kelly stake sizing
        kelly_df = kelly_table(edges_df, bankroll=bankroll, fraction=kelly_frac)
        disp["Kelly Stake"] = kelly_df["kelly_stake"].apply(lambda x: f"${x:.2f}" if x > 0 else "—")

        st.dataframe(
            disp.style.apply(highlight_edge, axis=1),
            hide_index=True,
            width='stretch'
        )

        # Download
        import io
        buf = io.StringIO()
        disp.to_csv(buf, index=False)
        st.download_button("Download Value Bets CSV", buf.getvalue(),
                           file_name="value_bets.csv", mime="text/csv")

st.divider()

# ── Try Scorer Value ───────────────────────────────────────────────────────
st.subheader("🏃 Try Scorer Value")
st.caption("Model probabilities for anytime try scorers across upcoming fixtures.")

if not player_df.empty and not upcoming.empty:
    from models.try_scorer import top_try_scorers_for_match
    final = matches_df[matches_df["status"] == "final"]

    try_model = fit_try_scorer_cached(
        len(player_df) + len(final), player_df, matches_df
    ) if len(final) >= 20 else None

    scorer_rows = []
    for _, m in upcoming.iterrows():
        preds = top_try_scorers_for_match(
            m["home_team_id"], m["away_team_id"], player_df, try_model, n=5
        )
        if preds.empty:
            continue
        preds["match_label"] = tname(m["home_team_id"]) + " vs " + tname(m["away_team_id"])
        preds["league"] = LEAGUES.get(m["league_id"], m["league_id"])
        scorer_rows.append(preds)

    if scorer_rows:
        all_scorers = pd.concat(scorer_rows, ignore_index=True)
        all_scorers["Team"] = all_scorers["team_id"].apply(tname)
        all_scorers["Model %"] = (all_scorers["prob"] * 100).round(1).astype(str) + "%"
        all_scorers["Model Odds"] = all_scorers["prob"].apply(
            lambda p: format_american(-round(p / (1 - p) * 100) if p > 0.5 else round((1 - p) / p * 100))
            if 0 < p < 1 else "—"
        )

        st.dataframe(
            all_scorers[[
                "match_label", "league", "player_name", "Team", "Model %", "Model Odds"
            ]].rename(columns={
                "match_label": "Match", "league": "League",
                "player_name": "Player",
            }),
            hide_index=True,
            width='stretch',
        )
    else:
        st.info("No try scorer predictions available. More match data needed.")
else:
    st.info("Try scorer model requires player stat data from completed matches.")

st.divider()

# ── Totals Analysis ────────────────────────────────────────────────────────
st.subheader("➕ Totals Analysis (Over/Under)")
if not upcoming.empty and not odds_df.empty:
    from models.dixon_coles import predict
    final = matches_df[matches_df["status"] == "final"]
    dc_model = fit_dc_cached(len(final), matches_df) if len(final) >= 15 else None

    lo = odds_df.sort_values("scraped_at").groupby("match_id").last().reset_index()
    totals_rows = []

    for _, m in upcoming.head(20).iterrows():
        o = lo[lo["match_id"] == m["id"]]
        if o.empty or pd.isna(o.iloc[0].get("total_line")):
            continue
        total_line = float(o.iloc[0]["total_line"])

        exp_total = None
        if dc_model:
            res = predict(m["home_team_id"], m["away_team_id"], dc_model)
            if res:
                exp_total = round(res["exp_home"] + res["exp_away"], 1)

        totals_rows.append({
            "Match":      tname(m["home_team_id"]) + " vs " + tname(m["away_team_id"]),
            "DK Line":    total_line,
            "Model Exp":  exp_total if exp_total else "—",
            "Over Odds":  format_american(o.iloc[0].get("total_over_odds")),
            "Under Odds": format_american(o.iloc[0].get("total_under_odds")),
            "Signal":     ("✅ Over" if exp_total and exp_total > total_line
                           else ("🔴 Under" if exp_total and exp_total < total_line
                                 else "—")),
        })

    if totals_rows:
        st.dataframe(pd.DataFrame(totals_rows), hide_index=True, width='stretch')
    else:
        st.info("No totals odds available for upcoming fixtures.")
else:
    st.info("Totals analysis requires odds data. Set ODDS_API_KEY and run the pipeline.")

st.divider()

# ── Parlay Builder ─────────────────────────────────────────────────────────
st.subheader("🎰 Parlay Builder (Informational)")
st.caption("Combine picks to see combined probability vs DraftKings parlay odds.")

picks = st.multiselect(
    "Add picks (enter as 'Team ML' strings or select from value bets above)",
    options=[],
    help="This feature will be populated from the value bets table once data is available.",
)

if not upcoming.empty and not elo_df.empty:
    ratings = current_ratings(elo_df) if not elo_df.empty else {}
    parlay_options = []
    for _, m in upcoming.head(10).iterrows():
        r_h = ratings.get(m["home_team_id"], 1500)
        r_a = ratings.get(m["away_team_id"], 1500)
        ph, _, pa = win_probability(r_h, r_a)
        parlay_options.append({
            "label": f"{tname(m['home_team_id'])} (home) — {ph:.1%}",
            "prob": ph,
        })
        parlay_options.append({
            "label": f"{tname(m['away_team_id'])} (away) — {pa:.1%}",
            "prob": pa,
        })

    selected_parlay = st.multiselect(
        "Select legs (model probability shown)",
        options=[p["label"] for p in parlay_options],
        key="parlay_legs",
    )

    if selected_parlay:
        selected_probs = [p["prob"] for p in parlay_options if p["label"] in selected_parlay]
        combined_prob  = 1.0
        for p in selected_probs:
            combined_prob *= p
        st.metric("Combined Model Probability", f"{combined_prob:.2%}")
        implied_parlay = 1 / combined_prob - 1
        american_parlay = round(implied_parlay * 100)
        st.metric("Fair Value Parlay Odds (American)", f"+{american_parlay}")
        st.caption("Compare this against DraftKings parlay odds for your selected legs.")

st.divider()

# ── Historical Edge Tracking ───────────────────────────────────────────────
st.subheader("📈 Historical Edge Tracking")
st.info(
    "Historical pick tracking will be populated automatically as the model makes "
    "predictions and results come in. This section will show ROI, strike rate, "
    "and calibration metrics by market type once sufficient data is available."
)
from footer import add_betting_oracle_footer
add_betting_oracle_footer()