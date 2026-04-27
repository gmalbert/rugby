"""
Page 4 — Match Analysis
Deep pre-match breakdown with Dixon-Coles predictions, H2H, and DK odds vs model.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from utils.cache import (
    load_teams, load_matches, load_player_stats,
    load_elo_ratings, load_odds,
    fit_dc_cached, fit_try_scorer_cached,
)
from utils.config import LEAGUES, OPEN_METEO_GEOCODING_BASE, OPEN_METEO_BASE, WMO_DESCRIPTIONS
from utils.charts import probability_bar, scoreline_heatmap, bar_chart
from utils.odds import american_to_implied, format_american
import models.dixon_coles as dc
import models.elo as elo_model
from models.try_scorer import top_try_scorers_for_match

st.title("🔬 Match Analysis")

# ── Load data ──────────────────────────────────────────────────────────────
teams_df   = load_teams()
matches_df = load_matches()
player_df  = load_player_stats()
elo_df     = load_elo_ratings()
odds_df    = load_odds()

if matches_df.empty:
    st.warning("No data loaded. Run `python data/pipeline.py` first.", icon="⚠️")
    st.stop()

_tmap = dict(zip(teams_df["id"], teams_df["name"])) if not teams_df.empty else {}
def tname(tid: str) -> str:
    return _tmap.get(tid, tid.split("-", 1)[-1].replace("-", " ").title())

# ── Fixture selector ───────────────────────────────────────────────────────
now        = datetime.now(timezone.utc)
in_14_days = now + timedelta(days=14)

upcoming = matches_df[
    (matches_df["kickoff_utc"] >= now) &
    (matches_df["kickoff_utc"] <= in_14_days) &
    (matches_df["status"] == "scheduled")
].sort_values("kickoff_utc")

if upcoming.empty:
    st.info("No upcoming fixtures in the next 14 days. Check back after the pipeline has run.")
    st.stop()

upcoming["label"] = (
    upcoming["kickoff_utc"].dt.strftime("%d %b %H:%M") + "  " +
    upcoming["home_team_id"].apply(tname) + " vs " +
    upcoming["away_team_id"].apply(tname)
)

selected_label = st.sidebar.selectbox("Select Fixture", upcoming["label"])
match = upcoming[upcoming["label"] == selected_label].iloc[0]

home_id  = match["home_team_id"]
away_id  = match["away_team_id"]
home_name = tname(home_id)
away_name = tname(away_id)

# ── Match preview card ─────────────────────────────────────────────────────
st.header(f"{home_name}  vs  {away_name}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("League",     LEAGUES.get(match["league_id"], match["league_id"]))
c2.metric("Kickoff",    pd.Timestamp(match["kickoff_utc"]).strftime("%d %b %Y %H:%M UTC"))
c3.metric("Venue",      str(match.get("venue", "TBC") or "TBC"))
c4.metric("Round",      int(match.get("round", 0) or 0))

st.divider()

# ── Models ─────────────────────────────────────────────────────────────────
# Elo win probs
elo_probs = None
if not elo_df.empty:
    ratings = elo_model.current_ratings(elo_df)
    r_h = ratings.get(home_id, 1500)
    r_a = ratings.get(away_id, 1500)
    elo_probs = elo_model.win_probability(r_h, r_a)

# Dixon-Coles
dc_result = None
final_matches = matches_df[matches_df["status"] == "final"]
if len(final_matches) >= 15:
    dc_model = fit_dc_cached(len(final_matches), matches_df)
    if dc_model:
        dc_result = dc.predict(home_id, away_id, dc_model)

# Try scorer model
try_model = None
scorer_preds = pd.DataFrame()
if not player_df.empty and len(final_matches) >= 20:
    try_model = fit_try_scorer_cached(
        len(player_df) + len(final_matches), player_df, matches_df
    )
    if try_model:
        scorer_preds = top_try_scorers_for_match(
            home_id, away_id, player_df, try_model, n=5
        )

# ── Win Probabilities ──────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🎲 Win Probabilities")

    if dc_result:
        probs = [dc_result["p_home"], dc_result["p_draw"], dc_result["p_away"]]
        source = "Dixon-Coles"
    elif elo_probs:
        probs = list(elo_probs)
        source = "Elo"
    else:
        probs = [0.5, 0.05, 0.45]
        source = "Default (no data)"

    fig = probability_bar(
        [home_name, "Draw", away_name],
        probs,
    )
    st.plotly_chart(fig, width='stretch')
    st.caption(f"Source: {source} model")

    if dc_result:
        st.subheader("🎯 Predicted Score")
        exp_h = round(dc_result["exp_home"], 1)
        exp_a = round(dc_result["exp_away"], 1)
        st.metric(f"Expected: {home_name}", exp_h)
        st.metric(f"Expected: {away_name}", exp_a)
        st.caption("Top 5 most likely scorelines:")
        for hs, as_, prob in dc_result["top_scorelines"]:
            st.write(f"  {home_name} {hs} – {as_} {away_name}  ({prob:.1%})")

with col_right:
    st.subheader("📊 Scoreline Distribution")
    if dc_result is not None and dc_result.get("matrix") is not None:
        fig = scoreline_heatmap(dc_result["matrix"], max_val=40)
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("Dixon-Coles model requires more historical match data to run.")

st.divider()

# ── Head-to-Head ───────────────────────────────────────────────────────────
st.subheader(f"⚔️ Last 5 Meetings")
h2h = matches_df[
    (
        ((matches_df["home_team_id"] == home_id) & (matches_df["away_team_id"] == away_id)) |
        ((matches_df["home_team_id"] == away_id) & (matches_df["away_team_id"] == home_id))
    ) & (matches_df["status"] == "final")
].sort_values("kickoff_utc", ascending=False).head(5)

if h2h.empty:
    st.info("No previous meetings on record.")
else:
    rows = []
    for _, row in h2h.iterrows():
        rows.append({
            "Date":  pd.Timestamp(row["kickoff_utc"]).strftime("%d %b %Y"),
            "Home":  tname(row["home_team_id"]),
            "Score": f"{row['home_score']}–{row['away_score']}",
            "Away":  tname(row["away_team_id"]),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')

st.divider()

# ── Key Stats Comparison ───────────────────────────────────────────────────
st.subheader("📏 Key Stats Comparison")
if not final_matches.empty:
    def team_stats(tid: str) -> dict:
        hm = final_matches[final_matches["home_team_id"] == tid]
        am = final_matches[final_matches["away_team_id"] == tid]
        n  = max(len(hm) + len(am), 1)
        tp = int(hm["home_score"].sum() + am["away_score"].sum())
        tt = int(hm["home_tries"].sum()  + am["away_tries"].sum())
        ta_c = int(hm["away_tries"].sum() + am["home_tries"].sum())
        wins = (
            (hm["home_score"] > hm["away_score"]).sum() +
            (am["away_score"] > am["home_score"]).sum()
        )
        if not player_df.empty:
            tp_rows = player_df[player_df["team_id"] == tid]
            metres     = int(tp_rows["metres_run"].sum())
            linebreaks = int(tp_rows["linebreaks"].sum())
            tackles    = int(tp_rows["tackles"].sum())
            missed     = int(tp_rows["missed_tackles"].sum())
        else:
            metres = linebreaks = tackles = missed = 0

        return {
            "Win %":          round(wins / n * 100, 1),
            "Pts/Game":       round(tp / n, 1),
            "Tries/Game":     round(tt / n, 2),
            "Tries Conceded/Game": round(ta_c / n, 2),
            "Metres/Game":    round(metres / n),
            "Linebreaks/Game": round(linebreaks / n, 1),
            "Tackles/Game":   round(tackles / n),
            "Missed Tackles/Game": round(missed / n, 1),
        }

    h_stats = team_stats(home_id)
    a_stats = team_stats(away_id)
    metrics = list(h_stats.keys())

    comp_df = pd.DataFrame({
        "Metric": metrics,
        home_name: [h_stats[m] for m in metrics],
        away_name: [a_stats[m] for m in metrics],
    })
    st.dataframe(comp_df, hide_index=True, width='stretch')
else:
    st.info("Stats comparison available once historical match data is loaded.")

st.divider()

# ── Predicted Try Scorers ──────────────────────────────────────────────────
st.subheader("🏃 Predicted Try Scorers")
if not scorer_preds.empty:
    scorer_preds["Team"] = scorer_preds["team_id"].apply(tname)
    scorer_preds["Prob"] = scorer_preds["prob"].apply(lambda p: f"{p:.1%}")
    st.dataframe(
        scorer_preds[["Team", "player_name", "Prob"]].rename(
            columns={"player_name": "Player"}
        ),
        hide_index=True, width='stretch',
    )
else:
    st.info("Try scorer predictions require player stat data from completed matches.")

st.divider()

# ── DK Odds vs Model ───────────────────────────────────────────────────────
st.subheader("💰 DraftKings Odds vs Model")

match_odds = pd.DataFrame()
if not odds_df.empty:
    lo = odds_df.sort_values("scraped_at").groupby("match_id").last().reset_index()
    match_odds = lo[lo["match_id"] == match["id"]]

if not match_odds.empty and dc_result:
    o = match_odds.iloc[0]
    rows = []
    for side, model_p, label, dk_ml in [
        ("home", dc_result["p_home"], f"{home_name} ML", o.get("home_ml")),
        ("away", dc_result["p_away"], f"{away_name} ML", o.get("away_ml")),
    ]:
        if pd.notna(dk_ml) and dk_ml:
            dk_imp = american_to_implied(float(dk_ml))
            edge   = model_p - dk_imp
            rows.append({
                "Market":       label,
                "DK Odds":      format_american(float(dk_ml)),
                "DK Implied %": f"{dk_imp:.1%}",
                "Model %":      f"{model_p:.1%}",
                "Edge":         f"{edge:+.1%}",
                "Signal":       "✅ Back" if edge >= 0.05 else ("🔴 Fade" if edge <= -0.05 else "—"),
            })

    total_line = o.get("total_line")
    if pd.notna(total_line) and dc_result:
        exp_total = dc_result["exp_home"] + dc_result["exp_away"]
        rows.append({
            "Market":       f"Total O/U {total_line}",
            "DK Odds":      "—",
            "DK Implied %": "—",
            "Model %":      f"exp. {exp_total:.1f} pts",
            "Edge":         f"{exp_total - float(total_line):+.1f} pts",
            "Signal":       "✅ Over" if exp_total > float(total_line) else "🔴 Under",
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    else:
        st.info("No odds data for this match.")
elif match_odds.empty:
    st.info("No DraftKings odds on record for this fixture. Odds load via The Odds API (set ODDS_API_KEY).")
else:
    st.info("Model predictions require more historical match data.")

# ── Weather widget ─────────────────────────────────────────────────────────
venue = str(match.get("venue", "") or "")
if venue:
    st.divider()
    st.subheader("🌦️ Venue Weather at Kickoff")
    import requests
    try:
        geo = requests.get(
            f"{OPEN_METEO_GEOCODING_BASE}/search",
            params={"name": venue, "count": 1, "language": "en", "format": "json"},
            timeout=5,
        ).json().get("results", [])
        if geo:
            lat, lon = geo[0]["latitude"], geo[0]["longitude"]
            wr = requests.get(
                f"{OPEN_METEO_BASE}/forecast",
                params={
                    "latitude":  lat,
                    "longitude": lon,
                    "current":   "temperature_2m,weather_code,wind_speed_10m,"
                                 "wind_direction_10m,precipitation,relative_humidity_2m",
                    "wind_speed_unit": "ms",
                    "forecast_days": 1,
                },
                timeout=5,
            )
            if wr.status_code == 200:
                c = wr.json().get("current", {})
                temp  = c.get("temperature_2m", "—")
                desc  = WMO_DESCRIPTIONS.get(c.get("weather_code", -1), "Unknown")
                wind  = c.get("wind_speed_10m", "—")
                rain  = c.get("precipitation", 0.0)
                humid = c.get("relative_humidity_2m", "—")
                col_w1, col_w2, col_w3, col_w4 = st.columns(4)
                col_w1.metric("Conditions", desc)
                col_w2.metric("Temperature", f"{temp}°C")
                col_w3.metric("Wind", f"{wind} m/s")
                col_w4.metric("Precipitation", f"{rain} mm")
            else:
                st.caption(f"Weather unavailable for '{venue}'.")
        else:
            st.caption(f"Could not geocode venue '{venue}'.")
    except Exception:
        st.caption("Weather service unavailable.")

from footer import add_betting_oracle_footer
add_betting_oracle_footer()
