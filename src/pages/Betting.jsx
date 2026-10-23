import { useState } from "react";
import {
  useApp,
  Sidebar,
  Title,
  Section,
  Info,
  Table,
  Select,
  Slider,
  NumberInput,
  MultiSelect,
  Metric,
  Chart,
} from "../ui.jsx";
import {
  american,
  chrono,
  fairOdds,
  implied,
  kellyStake,
  pct,
  predictMatch,
  winProbability,
} from "../analytics.js";
import Footer from "../Footer.jsx";

export default function Betting({ page }) {
  return page === "/Line_Movement" ? <Movement /> : <Edge />;
}
function Edge() {
  const { data, leagues, tname, odds, ratings } = useApp();
  const [edge, setEdge] = useState(5),
    [bankroll, setBankroll] = useState(1000),
    [fraction, setFraction] = useState(".5"),
    [legs, setLegs] = useState([]);
  const upcoming = data.matches
    .filter(
      (m) =>
        m.status === "scheduled" &&
        new Date(m.kickoff_utc) >= Date.now() &&
        new Date(m.kickoff_utc) <= Date.now() + 14 * 86400000 &&
        (!leagues.length || leagues.includes(m.league_id)),
    )
    .sort(chrono("kickoff_utc"));
  const predictions = upcoming.map((m) => ({
    m,
    p: predictMatch(m, data, ratings),
    o: odds[m.id],
  }));
  const bets = predictions
    .filter((x) => x.o)
    .flatMap(({ m, p, o }) =>
      ["home", "away"]
        .filter((side) => o[`${side}_ml`] != null)
        .map((side) => {
          const elo = winProbability(
            ratings[m.home_team_id],
            ratings[m.away_team_id],
          );
          const prob = elo[side],
            line = o[`${side}_ml`],
            diff = prob - implied(line);
          return {
            Match: `${tname(m.home_team_id)} v ${tname(m.away_team_id)}`,
            Pick: tname(m[`${side}_team_id`]),
            "DK ML": american(line),
            "Model %": pct(prob),
            "DK Implied": pct(implied(line)),
            "Edge %": pct(diff),
            "Kelly Stake ($)": kellyStake(
              prob,
              line,
              bankroll,
              Number(fraction),
            ),
            Signal:
              diff >= edge / 100
                ? "✅ Back"
                : diff <= -edge / 100
                  ? "🔴 Fade"
                  : "—",
            diff,
            _signal: diff >= edge / 100 ? "back" : "fade",
          };
        }),
    );
  const spread = [],
    totals = [];
  predictions
    .filter(({ p, o }) => p.matrix && o)
    .forEach(({ m, p, o }) => {
      const name = `${tname(m.home_team_id)} v ${tname(m.away_team_id)}`;
      if (o.total_line != null) {
        let over = 0,
          under = 0,
          push = 0;
        p.matrix.forEach((r, h) =>
          r.forEach((v, a) => {
            if (h + a > o.total_line) over += v;
            else if (h + a < o.total_line) under += v;
            else push += v;
          }),
        );
        totals.push({
          Match: name,
          "DK O/U": o.total_line,
          "Model Total": p.exp_home + p.exp_away,
          "Over %": pct(over),
          "Under %": pct(under),
          "Push %": pct(push),
          Signal: over > under ? "Over" : "Under",
        });
      }
      if (o.spread_home != null) {
        let cover = 0,
          push = 0;
        p.matrix.forEach((r, h) =>
          r.forEach((v, a) => {
            if (h + o.spread_home > a) cover += v;
            else if (h + o.spread_home === a) push += v;
          }),
        );
        spread.push({
          Match: name,
          "Home Spread": o.spread_home,
          Odds: american(o.spread_home_odds),
          "Cover %": pct(cover),
          "Push %": pct(push),
          Edge: o.spread_home_odds
            ? pct(cover - implied(o.spread_home_odds))
            : "—",
        });
      }
    });
  const legOptions = predictions.flatMap(({ m, p }) =>
    ["home", "away"].map((side) => ({
      value: `${m.id}:${side}`,
      label: `${tname(m[`${side}_team_id`])} to win`,
      p: p[side],
      match: m.id,
    })),
  );
  const selected = legs
      .map((id) => legOptions.find((l) => l.value === id))
      .filter(Boolean),
    duplicate = new Set(selected.map((l) => l.match)).size !== selected.length;
  const probability = selected.reduce((v, l) => v * l.p, 1);
  const scorers = predictions.flatMap(({ m }) =>
    (data.try_predictions?.[m.id] ?? []).map((s) => ({
      Match: `${tname(m.home_team_id)} vs ${tname(m.away_team_id)}`,
      Player: s.player_name,
      Team: tname(s.team_id),
      "Model %": pct(s.prob),
      "Model Odds": american(fairOdds(s.prob)),
    })),
  );
  const cols = bets[0]
    ? Object.keys(bets[0])
        .filter((k) => !["diff", "_signal"].includes(k))
        .map((k) => ({ key: k, label: k }))
    : [];
  return (
    <>
      <Sidebar>
        <Slider
          label="Min Edge %"
          min={1}
          max={20}
          value={edge}
          onChange={setEdge}
        />
        <NumberInput
          label="Bankroll ($)"
          min={10}
          max={100000}
          step={50}
          value={bankroll}
          onChange={setBankroll}
        />
        <Select
          label="Kelly Fraction"
          value={fraction}
          onChange={setFraction}
          options={[
            { value: ".25", label: "¼ Kelly" },
            { value: ".5", label: "½ Kelly" },
            { value: "1", label: "Full Kelly" },
          ]}
        />
      </Sidebar>
      <Title caption="Model-identified value vs bookmaker lines — informational only.">
        ⚡ Betting Edge
      </Title>
      <Section title="💎 Value Bets — Match Winner (ML)">
        {bets.length ? (
          <Table
            rows={bets
              .filter((b) => Math.abs(b.diff) >= edge / 100)
              .sort((a, b) => b.diff - a.diff)}
            columns={cols}
          />
        ) : (
          <Info>
            No odds available for upcoming fixtures in selected leagues.
          </Info>
        )}
      </Section>
      <Section title="📐 Spread Edges (Dixon-Coles vs BetMGM BR)">
        {spread.length ? (
          <Table rows={spread} />
        ) : (
          <Info>No spread odds available.</Info>
        )}
      </Section>
      <Section title="➕ Totals Analysis (Over/Under)">
        {totals.length ? (
          <Table rows={totals} />
        ) : (
          <Info>No totals odds available for analysis.</Info>
        )}
      </Section>
      <Section title="🏃 Try Scorer Value">
        {scorers.length ? (
          <Table rows={scorers} />
        ) : (
          <Info>
            No try scorer predictions available. More match data needed.
          </Info>
        )}
      </Section>
      <Section title="🎰 Parlay Builder (Informational)">
        <MultiSelect
          label="Select match-winner legs"
          value={legs}
          onChange={setLegs}
          options={legOptions}
        />
        {duplicate ? (
          <Info warning>Select only one outcome per fixture.</Info>
        ) : (
          !!selected.length && (
            <div className="columns">
              <Metric
                label="Combined model probability"
                value={pct(probability)}
              />
              <Metric
                label="Fair American odds"
                value={american(fairOdds(probability))}
              />
            </div>
          )
        )}
        <p className="caption">
          Combined probabilities assume independent match outcomes.
        </p>
      </Section>
      <Section title="📈 Historical Edge Tracking">
        <Info>
          ROI, strike rate, and calibration by market type will appear as
          settled results accumulate.
        </Info>
      </Section>
      <Footer />
    </>
  );
}
function Movement() {
  const { data, leagues, tname } = useApp(),
    [id, setId] = useState("");
  const now = Date.now(),
    relevant = data.matches
      .filter(
        (m) =>
          new Date(m.kickoff_utc) >= now - 3 * 86400000 &&
          new Date(m.kickoff_utc) <= now + 14 * 86400000 &&
          (!leagues.length || leagues.includes(m.league_id)),
      )
      .sort(chrono("kickoff_utc"));
  const m = relevant.find((m) => m.id === id) ?? relevant[0];
  const history = m
    ? data.odds.filter((o) => o.match_id === m.id).sort(chrono("scraped_at"))
    : [];
  const first = history[0],
    last = history.at(-1);
  return (
    <>
      <Title caption="Track how DraftKings odds shift from opening to kick-off — sharp money leaves a trail.">
        📉 Line Movement
      </Title>
      {!m ? (
        <Info>No fixtures in the current window for selected leagues.</Info>
      ) : (
        <>
          <Sidebar>
            <h2>Line Movement</h2>
            <Select
              label="Fixture"
              value={m.id}
              onChange={setId}
              options={relevant.map((x) => ({
                value: x.id,
                label: `${tname(x.home_team_id)} vs ${tname(x.away_team_id)} (${x.kickoff_utc.slice(0, 10)})`,
              }))}
            />
          </Sidebar>
          <h2>
            {tname(m.home_team_id)} vs {tname(m.away_team_id)}
          </h2>
          <p className="caption">
            Kickoff {new Date(m.kickoff_utc).toUTCString()}
          </p>
          {!history.length ? (
            <Info>No odds have been scraped for this fixture yet.</Info>
          ) : (
            <>
              <div className="columns three">
                <Metric
                  label="Opening Home ML"
                  value={american(first.home_ml)}
                />
                <Metric
                  label="Current Home ML"
                  value={american(last.home_ml)}
                />
                <Metric
                  label="Home ML Change"
                  value={
                    last.home_ml != null && first.home_ml != null
                      ? american(last.home_ml - first.home_ml)
                      : "—"
                  }
                />
              </div>
              {new Set(history.map((o) => o.scraped_at)).size < 2 && (
                <Info>
                  Only one odds snapshot is available. Movement charts populate
                  after another refresh.
                </Info>
              )}
              <Section title="💲 Moneyline Movement">
                <Chart
                  data={["home", "away"].map((side) => ({
                    type: "scatter",
                    mode: "lines+markers",
                    name: tname(m[`${side}_team_id`]),
                    x: history.map((o) => o.scraped_at),
                    y: history.map((o) => o[`${side}_ml`]),
                  }))}
                  layout={{
                    title: "Moneyline Movement",
                    yaxis: { title: { text: "American Odds" } },
                  }}
                />
              </Section>
              {history.some((o) => o.total_line != null) && (
                <Section title="➕ Total (O/U) Line Movement">
                  <Chart
                    data={[
                      {
                        type: "scatter",
                        mode: "lines+markers",
                        x: history.map((o) => o.scraped_at),
                        y: history.map((o) => o.total_line),
                      },
                    ]}
                    layout={{ title: "Total Line" }}
                  />
                </Section>
              )}
              <Section title="📋 All Snapshots">
                <Table
                  rows={history.map((o) => ({
                    Time: o.scraped_at,
                    "Home ML": american(o.home_ml),
                    "Away ML": american(o.away_ml),
                    "O/U": o.total_line,
                    Spread: o.spread_home,
                  }))}
                />
              </Section>
              <Section title="📊 Implied Probability Movement">
                <Chart
                  data={["home", "away"].map((side) => ({
                    type: "scatter",
                    mode: "lines+markers",
                    name: tname(m[`${side}_team_id`]),
                    x: history.map((o) => o.scraped_at),
                    y: history.map((o) => implied(o[`${side}_ml`])),
                  }))}
                  layout={{ yaxis: { tickformat: ".0%" } }}
                />
              </Section>
            </>
          )}
        </>
      )}
      <Footer />
    </>
  );
}
