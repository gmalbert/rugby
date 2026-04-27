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
    load_live_rugby_odds,
)
from utils.config import LEAGUES, ODDS_API_KEY, ODDS_API_IO_KEY
from utils.odds import american_to_implied, expected_value, format_american
from models.elo import current_ratings, win_probability
from models.value_finder import (
    find_match_edges, find_try_scorer_edges,
    find_live_match_edges, find_live_spread_edges, find_live_totals_edges,
)
from models.kelly import kelly_table

st.title("⚡ Betting Edge")
st.caption("Model-identified value vs bookmaker lines — informational only.")

# ── Load data ──────────────────────────────────────────────────────────────
teams_df   = load_teams()
matches_df = load_matches()
player_df  = load_player_stats()
elo_df     = load_elo_ratings()
odds_df    = load_odds()

DATA_DIR = 'data_files/'

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

# ── Live odds from odds-api.io ─────────────────────────────────────────────
live_odds_df = pd.DataFrame()
if ODDS_API_IO_KEY:
    live_odds_df = load_live_rugby_odds()

live_odds_available = not live_odds_df.empty

# ── Value Bets Table (ML) ─────────────────────────────────────────────────
st.subheader("💎 Value Bets — Match Winner (ML)")

# Try CSV-matched odds first, then fall back to live fuzzy-matched odds
edges_df = pd.DataFrame()

if not upcoming.empty and not elo_df.empty:
    # Source 1: pipeline-matched CSV odds
    if not odds_df.empty:
        edges_df = find_match_edges(upcoming, odds_df, elo_df, min_edge=min_edge)

    # Source 2: live odds-api.io (fills gaps where CSV has no match)
    if live_odds_available:
        live_edges = find_live_match_edges(
            upcoming, live_odds_df, elo_df, teams_df, min_edge=min_edge
        )
        if not live_edges.empty:
            # Merge, deduplicating by match+market (prefer CSV source)
            if not edges_df.empty:
                csv_keys = set(zip(edges_df["match_id"], edges_df["market"]))
                live_edges = live_edges[
                    ~live_edges.apply(
                        lambda r: (r["match_id"], r["market"]) in csv_keys, axis=1
                    )
                ]
            edges_df = pd.concat([edges_df, live_edges], ignore_index=True)

if edges_df.empty:
    if not live_odds_available and not ODDS_API_IO_KEY:
        st.info("Set `ODDS_API_IO_KEY` in `.env` to enable live odds from odds-api.io.")
    elif upcoming.empty:
        st.info("No fixtures in the next 14 days for the selected leagues.")
    elif elo_df.empty:
        st.info("Elo ratings not yet built. Run the pipeline first.")
    else:
        st.info(
            f"No ML edges ≥ {min_edge:.0%} found. "
            "DraftKings covers Super Rugby and NRL; BetMGM BR covers international fixtures. "
            "Premiership, Top 14, URC, and Champions Cup require a paid odds-api.io plan."
        )
else:
    edges_df["Home"]   = edges_df["home_team_id"].apply(tname)
    edges_df["Away"]   = edges_df["away_team_id"].apply(tname)
    edges_df["Match"]  = edges_df["Home"] + " vs " + edges_df["Away"]
    edges_df["League"] = edges_df["league_id"].map(LEAGUES).fillna(edges_df["league_id"])

    def highlight_edge(row):
        color = "#14532d" if row["Signal"] == "✅ Back" else "#7f1d1d"
        return [f"background-color: {color}"] * len(row)

    disp = edges_df[[
        "Match", "League", "market",
        "dk_odds", "dk_implied_pct", "model_pct", "edge_pct", "ev", "direction",
    ]].rename(columns={
        "market": "Market", "dk_odds": "Odds",
        "dk_implied_pct": "Book Impl %", "model_pct": "Elo %",
        "edge_pct": "Edge %", "ev": "EV ($1)", "direction": "Signal",
    })
    disp["Signal"] = disp["Signal"].map({"back": "✅ Back", "fade": "🔴 Fade"})

    kelly_df = kelly_table(edges_df, bankroll=bankroll, fraction=kelly_frac)
    disp["Kelly Stake"] = kelly_df["kelly_stake"].apply(lambda x: f"${x:.2f}" if x > 0 else "—")

    st.dataframe(disp.style.apply(highlight_edge, axis=1), hide_index=True, width='stretch')

    import io
    buf = io.StringIO()
    disp.to_csv(buf, index=False)
    st.download_button("Download Value Bets CSV", buf.getvalue(),
                       file_name="value_bets.csv", mime="text/csv")

if live_odds_available:
    st.caption(
        f"Live odds from odds-api.io — DraftKings (Super Rugby, NRL) "
        f"and BetMGM BR (international rugby). "
        f"{len(live_odds_df)} events with coverage."
    )

st.divider()

# ── Spread Edges ──────────────────────────────────────────────────────────
st.subheader("📐 Spread Edges (Dixon-Coles vs BetMGM BR)")
st.caption(
    "Compares DC model's expected margin to the BetMGM BR spread line. "
    "Edge flagged when model margin differs from book line by ≥ 3 pts."
)

final = matches_df[matches_df["status"] == "final"]
dc_model = fit_dc_cached(len(final), matches_df) if len(final) >= 15 else None

if not live_odds_available:
    st.info("Live odds not available. Set `ODDS_API_IO_KEY` in `.env`.")
elif dc_model is None:
    st.info("Dixon-Coles model needs ≥ 15 completed matches. Run the pipeline.")
elif upcoming.empty:
    st.info("No upcoming fixtures.")
else:
    spread_edges = find_live_spread_edges(
        upcoming, live_odds_df, dc_model, teams_df, min_edge=min_edge
    )
    if spread_edges.empty:
        st.info("No spread edges found. BetMGM BR covers international rugby fixtures only.")
    else:
        spread_edges["Home"]   = spread_edges["home_team_id"].apply(tname)
        spread_edges["Away"]   = spread_edges["away_team_id"].apply(tname)
        spread_edges["Match"]  = spread_edges["Home"] + " vs " + spread_edges["Away"]
        spread_edges["League"] = spread_edges["league_id"].map(LEAGUES).fillna(spread_edges["league_id"])

        def highlight_spread(row):
            color = "#14532d" if "home" in str(row.get("direction", "")) else "#7f1d1d"
            return [f"background-color: {color}"] * len(row)

        s_disp = spread_edges[[
            "Match", "League", "market", "bookmaker",
            "dc_margin", "book_margin", "point_edge", "dk_odds", "ev", "direction",
        ]].rename(columns={
            "market": "Market", "bookmaker": "Bookmaker",
            "dc_margin": "DC Margin", "book_margin": "Book Margin",
            "point_edge": "Pt Edge", "dk_odds": "Odds", "ev": "EV ($1)",
            "direction": "Signal",
        })
        s_disp["Signal"] = s_disp["Signal"].map({
            "back_home": "✅ Back Home",
            "back_away": "✅ Back Away",
        })
        st.dataframe(s_disp.style.apply(highlight_spread, axis=1), hide_index=True, width='stretch')

st.divider()

# ── Totals Analysis ───────────────────────────────────────────────────────
st.subheader("➕ Totals Analysis (Over/Under)")
st.caption("DC expected total vs BetMGM BR line. Signals when model and book differ by > 3 pts.")

if not live_odds_available:
    st.info("Live odds not available. Set `ODDS_API_IO_KEY` in `.env`.")
elif upcoming.empty:
    st.info("No upcoming fixtures.")
else:
    totals_df = find_live_totals_edges(upcoming, live_odds_df, dc_model, teams_df)

    if totals_df.empty:
        # Fall back to CSV odds if live has nothing
        if not odds_df.empty:
            lo = odds_df.sort_values("scraped_at").groupby("match_id").last().reset_index()
            totals_rows = []
            for _, m in upcoming.head(20).iterrows():
                o = lo[lo["match_id"] == m["id"]]
                if o.empty or pd.isna(o.iloc[0].get("total_line")):
                    continue
                total_line = float(o.iloc[0]["total_line"])
                exp_total = None
                if dc_model:
                    from models.dixon_coles import predict
                    res = predict(m["home_team_id"], m["away_team_id"], dc_model)
                    if res:
                        exp_total = round(res["exp_home"] + res["exp_away"], 1)
                totals_rows.append({
                    "Match":      tname(m["home_team_id"]) + " vs " + tname(m["away_team_id"]),
                    "DK Line":    total_line,
                    "Model Exp":  exp_total if exp_total else "—",
                    "Over Odds":  format_american(o.iloc[0].get("total_over_odds")),
                    "Under Odds": format_american(o.iloc[0].get("total_under_odds")),
                    "Signal":     ("✅ Over" if exp_total and exp_total > total_line + 3
                                   else ("🔴 Under" if exp_total and exp_total < total_line - 3
                                         else "⚖️ Push" if exp_total else "—")),
                })
            if totals_rows:
                st.dataframe(pd.DataFrame(totals_rows), hide_index=True, width='stretch')
            else:
                st.info("No totals odds available. BetMGM BR covers international fixtures only.")
        else:
            st.info("No totals odds available. BetMGM BR covers international rugby fixtures only.")
    else:
        totals_df["Home"]   = totals_df["home_team_id"].apply(tname)
        totals_df["Away"]   = totals_df["away_team_id"].apply(tname)
        totals_df["Match"]  = totals_df["Home"] + " vs " + totals_df["Away"]
        totals_df["League"] = totals_df["league_id"].map(LEAGUES).fillna(totals_df["league_id"])

        def highlight_totals(row):
            if row["signal"] == "✅ Over":
                return ["background-color: #14532d"] * len(row)
            if row["signal"] == "🔴 Under":
                return ["background-color: #7f1d1d"] * len(row)
            return [""] * len(row)

        t_disp = totals_df[[
            "Match", "League", "bookmaker", "total_line",
            "over_odds", "under_odds", "dc_exp_total", "signal",
        ]].rename(columns={
            "bookmaker": "Bookmaker", "total_line": "O/U Line",
            "over_odds": "Over Odds", "under_odds": "Under Odds",
            "dc_exp_total": "DC Expected", "signal": "Signal",
        })
        st.dataframe(t_disp.style.apply(highlight_totals, axis=1), hide_index=True, width='stretch')

st.divider()

# ── Try Scorer Value ───────────────────────────────────────────────────────
st.subheader("🏃 Try Scorer Value")
st.caption("Model probabilities for anytime try scorers across upcoming fixtures.")

if not player_df.empty and not upcoming.empty:
    from models.try_scorer import top_try_scorers_for_match

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

# ── Parlay Builder ─────────────────────────────────────────────────────────
st.subheader("🎰 Parlay Builder (Informational)")
st.caption("Combine picks to see combined probability vs DraftKings parlay odds.")

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
