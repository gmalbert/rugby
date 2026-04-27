"""
Page 6 — Model Lab
Elo leaderboard, Dixon-Coles parameters, backtesting, manual overrides, simulation.
"""

import streamlit as st
import pandas as pd
import numpy as np

from utils.cache import (
    load_teams, load_matches, load_elo_ratings, load_team_season_stats,
    load_bradley_terry_ratings, load_dc_params, fit_bt_cached, fit_dc_cached,
)
from utils.config import LEAGUES, ELO_K, ELO_HOME_ADV, ELO_DEFAULT
from utils.charts import elo_line_chart, histogram, probability_bar, scatter_chart
import models.elo as elo_model
import models.dixon_coles as dc
import models.bradley_terry as bt
from models.season_sim import simulate_season
from scipy.stats import poisson

st.title("🧪 Model Lab")
st.caption("Transparent view of the underlying models — tweak parameters and run simulations.")

# ── Load data ──────────────────────────────────────────────────────────────
teams_df   = load_teams()
matches_df = load_matches()
elo_df     = load_elo_ratings()
tss_df     = load_team_season_stats()

_tmap = dict(zip(teams_df["id"], teams_df["name"])) if not teams_df.empty else {}
def tname(tid: str) -> str:
    return _tmap.get(tid, tid.split("-", 1)[-1].replace("-", " ").title())

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Elo Leaderboard",
    "⚙️ Dixon-Coles Params",
    "📉 Backtesting",
    "🎛️ Manual Override",
    "🎲 Match Simulation",
    "🏆 Bradley-Terry",
    "📅 Season Simulation",
])

# ── Tab 1: Elo Leaderboard ─────────────────────────────────────────────────
with tab1:
    st.subheader("Elo Leaderboard — Current Ratings")
    if elo_df.empty:
        st.info("Elo ratings are calculated by the pipeline after match results come in.")
    else:
        current = elo_model.current_ratings(elo_df).reset_index()
        current.columns = ["team_id", "rating"]
        current["Team"]   = current["team_id"].apply(tname)
        current["Rating"] = current["rating"].round(0).astype(int)

        # Trend: change over last 3 matches
        elo_sorted = elo_df.sort_values("date")
        trend = (
            elo_sorted.groupby("team_id")
              .apply(lambda g: g["rating"].iloc[-1] - g["rating"].iloc[max(-4, -len(g))])
              .rename("trend")
              .reset_index()
        )
        current = current.merge(trend, on="team_id", how="left")
        current["Trend"] = current["trend"].apply(
            lambda x: f"↑{x:+.0f}" if x > 5 else (f"↓{x:+.0f}" if x < -5 else "→")
        )

        league_col = elo_df.drop_duplicates("team_id").set_index("team_id")["league_id"]
        current["League"] = current["team_id"].map(league_col).map(LEAGUES).fillna("—")

        st.dataframe(
            current[["Team", "League", "Rating", "Trend"]]
                .sort_values("Rating", ascending=False)
                .reset_index(drop=True),
            width='stretch', hide_index=True,
        )

        # Elo history chart for selected team
        st.subheader("Elo History — Team")
        selected = st.selectbox("Select team", current["Team"].tolist())
        sel_id   = current[current["Team"] == selected]["team_id"].iloc[0]
        team_elo = elo_df[elo_df["team_id"] == sel_id]
        if not team_elo.empty:
            st.plotly_chart(elo_line_chart(team_elo, selected), width='stretch')

# ── Tab 2: Dixon-Coles Parameters ─────────────────────────────────────────
with tab2:
    st.subheader("Dixon-Coles Attack / Defence Ratings")
    final = matches_df[matches_df["status"] == "final"] if not matches_df.empty else pd.DataFrame()

    if len(final) < 15:
        st.info("Dixon-Coles model requires at least 15 completed matches to fit.")
    else:
        dc_model = fit_dc_cached(len(final), matches_df)

        if dc_model is None:
            st.error("Model fitting did not converge. More data may be needed.")
        else:
            st.caption(f"Home advantage parameter: **{dc_model['home_adv']:.3f}** | "
                       f"Rho (DC correction): **{dc_model['rho']:.3f}**")
            param_df = dc.params_df(dc_model, teams_df)
            st.dataframe(
                param_df[["team", "attack", "defence"]].rename(columns={"team": "Team"}),
                hide_index=True, width='stretch',
            )
            # Scatter: attack vs defence
            if not param_df.empty:
                fig = scatter_chart(param_df, x="attack", y="defence", text="team",
                                    title="Attack vs Defence Rating (higher attack = better attack; lower defence = better defence)")
                st.plotly_chart(fig, width='stretch')

# ── Tab 3: Backtesting ─────────────────────────────────────────────────────
with tab3:
    st.subheader("Model Backtesting")
    st.caption("Evaluate model accuracy on historical match data.")

    if matches_df.empty:
        st.info("No data available for backtesting.")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            backtest_league = st.selectbox(
                "League", ["All"] + list(LEAGUES.keys()),
                format_func=lambda x: "All Leagues" if x == "All" else LEAGUES[x],
            )
        with col_b:
            min_matches = st.slider("Min training matches", 10, 100, 30)

        bt_matches = matches_df[matches_df["status"] == "final"].copy()
        if backtest_league != "All":
            bt_matches = bt_matches[bt_matches["league_id"] == backtest_league]

        if len(bt_matches) < min_matches + 5:
            st.info(f"Need at least {min_matches + 5} completed matches. Found {len(bt_matches)}.")
        else:
            bt_matches = bt_matches.sort_values("kickoff_utc").reset_index(drop=True)
            split      = min_matches

            train_m = bt_matches.iloc[:split]
            test_m  = bt_matches.iloc[split:]

            elo_bt  = elo_model.build_elo_history(train_m)
            ratings = elo_model.current_ratings(elo_bt)

            results = []
            for _, row in test_m.iterrows():
                r_h = ratings.get(row["home_team_id"], ELO_DEFAULT)
                r_a = ratings.get(row["away_team_id"], ELO_DEFAULT)
                ph, pd_, pa = elo_model.win_probability(r_h, r_a)

                actual = (1 if row["home_score"] > row["away_score"]
                          else (0 if row["home_score"] < row["away_score"] else 0.5))
                pred_winner = "home" if ph > pa else "away"
                correct     = (actual == 1 and pred_winner == "home") or \
                              (actual == 0 and pred_winner == "away")

                brier_home = (ph - (1 if actual == 1 else 0)) ** 2
                results.append({
                    "correct": correct,
                    "brier":   brier_home,
                    "p_home":  ph,
                    "actual":  actual,
                })

                # Update ratings after prediction
                new_h, new_a = elo_model.update_elo(r_h, r_a, actual, home=True,
                                                     point_diff=abs(int(row["home_score"]) - int(row["away_score"])))
                ratings[row["home_team_id"]] = new_h
                ratings[row["away_team_id"]] = new_a

            res_df = pd.DataFrame(results)
            accuracy    = res_df["correct"].mean()
            brier_score = res_df["brier"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("% Correct Winner", f"{accuracy:.1%}")
            c2.metric("Brier Score", f"{brier_score:.4f}", help="Lower is better. 0.25 = random.")
            c3.metric("Test Matches", len(res_df))

            # Calibration scatter
            bins    = pd.cut(res_df["p_home"], bins=10)
            calib   = res_df.groupby(bins).agg(
                mean_pred=("p_home", "mean"),
                mean_actual=("actual", "mean"),
            ).reset_index()
            fig = scatter_chart(calib, x="mean_pred", y="mean_actual",
                                title="Calibration — Predicted vs Actual Home Win Rate")
            fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1,
                          line=dict(dash="dash", color="gray"))
            st.plotly_chart(fig, width='stretch')

# ── Tab 4: Manual Override ─────────────────────────────────────────────────
with tab4:
    st.subheader("Manual Rating Override")
    st.caption("Adjust team strengths for injury news or squad changes to see updated predictions.")

    if elo_df.empty or teams_df.empty:
        st.info("Load Elo data first (run pipeline).")
    else:
        base_ratings = elo_model.current_ratings(elo_df).to_dict()
        all_team_names = sorted(_tmap.values())

        col_h, col_a = st.columns(2)
        with col_h:
            home_team  = st.selectbox("Home Team", all_team_names, key="ov_home")
            home_adj   = st.slider(f"{home_team} adjustment", -200, 200, 0, step=10)
        with col_a:
            away_team  = st.selectbox("Away Team", [t for t in all_team_names if t != home_team], key="ov_away")
            away_adj   = st.slider(f"{away_team} adjustment", -200, 200, 0, step=10)

        h_id = next((k for k, v in _tmap.items() if v == home_team), None)
        a_id = next((k for k, v in _tmap.items() if v == away_team), None)

        if h_id and a_id:
            r_h = base_ratings.get(h_id, ELO_DEFAULT) + home_adj
            r_a = base_ratings.get(a_id, ELO_DEFAULT) + away_adj
            ph, pd_, pa = elo_model.win_probability(r_h, r_a)

            st.subheader("Updated Predictions")
            cm1, cm2, cm3 = st.columns(3)
            cm1.metric(f"{home_team} win", f"{ph:.1%}")
            cm2.metric("Draw",            f"{pd_:.1%}")
            cm3.metric(f"{away_team} win", f"{pa:.1%}")

            fig = probability_bar([home_team, "Draw", away_team], [ph, pd_, pa])
            st.plotly_chart(fig, width='stretch')

            st.caption(
                f"Base Elo: {home_team} {int(r_h - home_adj)}, {away_team} {int(r_a - away_adj)} "
                f"| After adjustment: {int(r_h)}, {int(r_a)}"
            )

# ── Tab 5: Monte Carlo Simulation ─────────────────────────────────────────
with tab5:
    st.subheader("Monte Carlo Match Simulation")
    st.caption("Run 10,000 simulations to see the full scoreline distribution.")

    final_mc = matches_df[matches_df["status"] == "final"] if not matches_df.empty else pd.DataFrame()
    dc_mc_model = None
    if len(final_mc) >= 15:
        dc_mc_model = fit_dc_cached(len(final_mc), matches_df)

    if not teams_df.empty:
        all_tnames = sorted(_tmap.values())
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            sim_home = st.selectbox("Home Team", all_tnames, key="sim_home")
        with col_s2:
            sim_away = st.selectbox("Away Team",
                                    [t for t in all_tnames if t != sim_home], key="sim_away")

        n_sims = st.slider("Simulations", 1000, 10000, 5000, step=1000)

        if st.button("▶  Run Simulation"):
            h_id_s = next((k for k, v in _tmap.items() if v == sim_home), None)
            a_id_s = next((k for k, v in _tmap.items() if v == sim_away), None)

            if dc_mc_model and h_id_s and a_id_s:
                res = dc.predict(h_id_s, a_id_s, dc_mc_model)
                if res:
                    mu_h = res["exp_home"]
                    mu_a = res["exp_away"]
                else:
                    mu_h, mu_a = 25.0, 20.0
            else:
                r_h  = elo_model.current_ratings(elo_df).get(h_id_s, ELO_DEFAULT) if not elo_df.empty else ELO_DEFAULT
                r_a  = elo_model.current_ratings(elo_df).get(a_id_s, ELO_DEFAULT) if not elo_df.empty else ELO_DEFAULT
                mu_h, mu_a = 25.0 * elo_model.win_probability(r_h, r_a)[0] * 2, \
                             25.0 * elo_model.win_probability(r_h, r_a)[2] * 2

            rng     = np.random.default_rng(42)
            h_scores = rng.poisson(mu_h, n_sims)
            a_scores = rng.poisson(mu_a, n_sims)
            totals   = h_scores + a_scores
            margins  = h_scores - a_scores

            h_wins   = (h_scores > a_scores).sum() / n_sims
            draws    = (h_scores == a_scores).sum() / n_sims
            a_wins   = (a_scores > h_scores).sum() / n_sims

            c1, c2, c3 = st.columns(3)
            c1.metric(f"{sim_home} Win",  f"{h_wins:.1%}")
            c2.metric("Draw",             f"{draws:.1%}")
            c3.metric(f"{sim_away} Win",  f"{a_wins:.1%}")
            st.caption(f"Expected: {sim_home} {mu_h:.1f} – {mu_a:.1f} {sim_away}")

            col_sim_a, col_sim_b = st.columns(2)
            with col_sim_a:
                fig = histogram(list(totals), title="Total Points Distribution", xaxis_title="Points")
                st.plotly_chart(fig, width='stretch')
            with col_sim_b:
                fig = histogram(list(margins), title="Winning Margin Distribution", xaxis_title="Margin (positive = home win)")
                st.plotly_chart(fig, width='stretch')
        else:
            st.info("Click **Run Simulation** to generate results.")
    else:
        st.info("Load team data first (run pipeline).")

# ── Tab 6: Bradley-Terry ────────────────────────────────────────────────────
with tab6:
    st.subheader("Bradley-Terry Team Strengths")
    st.caption(
        "Maximum-likelihood pairwise comparison model. More statistically principled "
        "than Elo for round-robin competitions as it uses the full fixture list simultaneously."
    )
    final_bt = matches_df[matches_df["status"] == "final"] if not matches_df.empty else pd.DataFrame()

    if len(final_bt) < 5:
        st.info("Bradley-Terry requires at least 5 completed matches.")
    else:
        # Use precomputed file first; fall back to live fit
        bt_df = load_bradley_terry_ratings()
        if bt_df.empty:
            with st.spinner("Fitting Bradley-Terry model…"):
                matches_hash = len(final_bt)
                bt_model = fit_bt_cached(matches_hash, final_bt)
            if bt_model:
                bt_df = bt.ratings_df(bt_model, teams_df)
            else:
                st.error("Model did not converge.")

        if not bt_df.empty:
            col_bt = "bt_strength" if "bt_strength" in bt_df.columns else bt_df.columns[-1]
            bt_df["Team"] = bt_df["team_id"].apply(tname) if "team" not in bt_df.columns else bt_df["team"]
            bt_df["Strength"] = bt_df[col_bt].round(3)
            bt_df["Rank"] = range(1, len(bt_df) + 1)
            st.dataframe(
                bt_df[["Rank", "Team", "Strength"]].reset_index(drop=True),
                hide_index=True,
                width='stretch',
            )

            st.subheader("Win Probability Calculator")
            all_bt_teams = bt_df["Team"].tolist()
            col_bh, col_ba = st.columns(2)
            with col_bh:
                bt_home = st.selectbox("Home Team", all_bt_teams, key="bt_home")
            with col_ba:
                bt_away = st.selectbox("Away Team", [t for t in all_bt_teams if t != bt_home], key="bt_away")

            bt_home_id = bt_df[bt_df["Team"] == bt_home]["team_id"].iloc[0]
            bt_away_id = bt_df[bt_df["Team"] == bt_away]["team_id"].iloc[0]

            # Rebuild model dict for win_probability
            strength_map = dict(zip(bt_df["team_id"], bt_df[col_bt]))
            bt_model_dict = {"teams": strength_map, "home_adv": 0.5}
            p_h, p_a = bt.win_probability(bt_home_id, bt_away_id, bt_model_dict)

            cm1, cm2 = st.columns(2)
            cm1.metric(f"{bt_home} win", f"{p_h:.1%}")
            cm2.metric(f"{bt_away} win", f"{p_a:.1%}")
            fig = probability_bar([bt_home, bt_away], [p_h, p_a])
            st.plotly_chart(fig, width='stretch')

# ── Tab 7: Season Simulation ───────────────────────────────────────────────
with tab7:
    st.subheader("Monte Carlo Season Simulation")
    st.caption(
        "Simulate all remaining fixtures 10 000 times using Elo win probabilities "
        "to produce finish-position probability tables."
    )

    if matches_df.empty or elo_df.empty:
        st.info("Season simulation requires match data and Elo ratings.")
    else:
        sim_league = st.selectbox(
            "League",
            options=list(LEAGUES.keys()),
            format_func=lambda x: LEAGUES[x],
            key="season_sim_league",
        )
        n_season_sims = st.slider("Simulations", 1_000, 20_000, 10_000, step=1_000)

        from datetime import datetime, timezone
        now_ss = datetime.now(timezone.utc)
        remaining = matches_df[
            (matches_df["league_id"] == sim_league) &
            (matches_df["status"] == "scheduled") &
            (matches_df["kickoff_utc"] >= now_ss)
        ].copy()
        current_table = tss_df[tss_df["league_id"] == sim_league].copy() if not tss_df.empty else pd.DataFrame()

        if remaining.empty:
            st.info("No remaining scheduled fixtures for this league.")
        elif st.button("▶ Run Season Simulation", key="run_season_sim"):
            with st.spinner("Simulating season…"):
                result = simulate_season(remaining, elo_df, current_table, n_sims=n_season_sims)

            if result.empty:
                st.warning("Simulation returned no results.")
            else:
                result["Team"] = result["team_id"].apply(tname)
                result["Winner %"] = (result["winner_prob"] * 100).round(1).astype(str) + "%"
                result["Top 4 %"]  = (result["top4_prob"]   * 100).round(1).astype(str) + "%"

                # Position probability heatmap
                pos_cols = [c for c in result.columns if c.startswith("P") and c[1:].isdigit()]
                heatmap_data = result.set_index("Team")[pos_cols].astype(float)

                import plotly.express as px
                fig_ss = px.imshow(
                    heatmap_data * 100,
                    labels=dict(x="Finish Position", y="Team", color="Probability %"),
                    color_continuous_scale="Blues",
                    title="Finish Position Probability (%)",
                    aspect="auto",
                )
                fig_ss.update_layout(height=max(300, len(result) * 35))
                st.plotly_chart(fig_ss, width='stretch')

                st.subheader("Summary")
                st.dataframe(
                    result[["Team", "Winner %", "Top 4 %"]].reset_index(drop=True),
                    hide_index=True,
                    width='stretch',
                )
from footer import add_betting_oracle_footer
add_betting_oracle_footer()