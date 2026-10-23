import { useMemo, useState } from "react";
import {
  useApp,
  Sidebar,
  Title,
  Section,
  Info,
  Table,
  Select,
  Slider,
  Metric,
  Chart,
  Bars,
  Probability,
} from "../ui.jsx";
import {
  backtest,
  chrono,
  fmt,
  mean,
  pct,
  predictMatch,
  simulateBracket,
  simulateMatch,
  simulateSeason,
  winProbability,
} from "../analytics.js";
import Footer from "../Footer.jsx";

const tabs = [
  "📊 Elo Leaderboard",
  "⚙️ Dixon-Coles Params",
  "📉 Backtesting",
  "🎛️ Manual Override",
  "🎲 Match Simulation",
  "🏆 Bradley-Terry",
  "📅 Season Simulation",
];
export default function Models({ page }) {
  return page === "/Tournament_Sim" ? <Tournament /> : <Lab />;
}
function Lab() {
  const [tab, setTab] = useState(0);
  return (
    <>
      <Title caption="Transparent view of the underlying models — tweak parameters and run simulations.">
        🧪 Model Lab
      </Title>
      <div className="tabs" role="tablist" aria-label="Model Lab">
        {tabs.map((t, i) => (
          <button
            key={t}
            role="tab"
            id={`tab-${i}`}
            aria-controls="model-panel"
            aria-selected={tab === i}
            onClick={() => setTab(i)}
            onKeyDown={(e) => {
              if (["ArrowRight", "ArrowLeft"].includes(e.key)) {
                e.preventDefault();
                const next =
                  (tab + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) %
                  tabs.length;
                setTab(next);
                document.getElementById(`tab-${next}`)?.focus();
              }
            }}
          >
            {t}
          </button>
        ))}
      </div>
      <div id="model-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === 0 ? (
          <Elo />
        ) : tab === 1 ? (
          <DC />
        ) : tab === 2 ? (
          <Backtest />
        ) : tab === 3 ? (
          <Override />
        ) : tab === 4 ? (
          <MatchSimulation />
        ) : tab === 5 ? (
          <BradleyTerry />
        ) : (
          <Season />
        )}
      </div>
      <Footer />
    </>
  );
}
function Elo() {
  const { data, ratings, tname, leagueNames } = useApp(),
    [team, setTeam] = useState("");
  const rows = Object.entries(ratings)
    .sort((a, b) => b[1] - a[1])
    .map(([id, rating]) => ({
      id,
      Team: tname(id),
      League: leagueNames[data.teams.find((t) => t.id === id)?.league_id],
      Elo: rating,
      Trend: (() => {
        const rs = data.elo
          .filter((e) => e.team_id === id)
          .sort(chrono("date"));
        const d = rs.at(-1)?.rating - rs.at(-4)?.rating;
        return d > 0 ? "↑" : d < 0 ? "↓" : "→";
      })(),
    }));
  const id = rows.some((r) => r.id === team) ? team : rows[0]?.id;
  const history = data.elo.filter((r) => r.team_id === id).sort(chrono("date"));
  return (
    <>
      <Section title="Elo Leaderboard — Current Ratings">
        <Table
          rows={rows}
          columns={["Team", "League", "Elo", "Trend"].map((k) => ({
            key: k,
            label: k,
          }))}
        />
      </Section>
      <Section title="Elo History — Team">
        <Select
          label="Select team"
          value={id}
          onChange={setTeam}
          options={rows.map((r) => ({ value: r.id, label: r.Team }))}
        />
        <Chart
          data={[
            {
              type: "scatter",
              mode: "lines",
              x: history.map((r) => r.date),
              y: history.map((r) => r.rating),
              line: { color: "#5a9e10" },
            },
          ]}
          layout={{ title: `Elo Rating — ${tname(id)}` }}
        />
      </Section>
    </>
  );
}
function DC() {
  const { data } = useApp();
  return (
    <Section title="Dixon-Coles Attack / Defence Ratings">
      {data.dc_model && (
        <div className="columns">
          <Metric label="Home Advantage" value={fmt(data.dc_model.home_adv)} />
          <Metric
            label="ρ (low-score correction)"
            value={fmt(data.dc_model.rho)}
          />
        </div>
      )}
      <Table
        rows={data.dc_params}
        columns={["team", "attack", "defence"].map((k) => ({
          key: k,
          label: k[0].toUpperCase() + k.slice(1),
        }))}
      />
      <Chart
        data={[
          {
            type: "scatter",
            mode: "markers+text",
            x: data.dc_params.map((r) => r.attack),
            y: data.dc_params.map((r) => r.defence),
            text: data.dc_params.map((r) => r.team),
            textposition: "top center",
          },
        ]}
        layout={{
          title: "Attack vs Defence",
          xaxis: { title: { text: "Attack" } },
          yaxis: { title: { text: "Defence" } },
        }}
      />
    </Section>
  );
}
function Backtest() {
  const { data } = useApp(),
    [league, setLeague] = useState("all"),
    [min, setMin] = useState(30);
  const results = useMemo(
    () =>
      backtest(
        data.matches.filter((m) => league === "all" || m.league_id === league),
        min,
      ),
    [data.matches, league, min],
  );
  const bins = Array.from({ length: 10 }, (_, i) => {
    const rs = results.filter((r) => r.p >= i / 10 && r.p < (i + 1) / 10);
    return {
      predicted: mean(rs, "p"),
      actual: mean(rs, "actual"),
      n: rs.length,
    };
  }).filter((b) => b.n);
  return (
    <Section title="Model Backtesting">
      <div className="columns">
        <Select
          label="League"
          value={league}
          onChange={setLeague}
          options={[
            { value: "all", label: "All leagues" },
            ...data.leagues.map((l) => ({ value: l.id, label: l.name })),
          ]}
        />
        <Slider
          label="Min training matches"
          value={min}
          onChange={setMin}
          min={10}
          max={100}
        />
      </div>
      {results.length ? (
        <>
          <div className="columns three">
            <Metric
              label="Correct Winner"
              value={pct(
                results.filter((r) => r.correct).length / results.length,
              )}
            />
            <Metric
              label="Brier Score"
              value={fmt(
                results.reduce((s, r) => s + (r.p - r.actual) ** 2, 0) /
                  results.length,
              )}
            />
            <Metric label="Test Matches" value={results.length} />
          </div>
          <Chart
            data={[
              {
                type: "scatter",
                mode: "markers",
                x: bins.map((b) => b.predicted),
                y: bins.map((b) => b.actual),
                marker: {
                  size: bins.map((b) => Math.max(8, Math.sqrt(b.n) * 4)),
                },
                name: "Calibration",
              },
              {
                type: "scatter",
                mode: "lines",
                x: [0, 1],
                y: [0, 1],
                line: { dash: "dash", color: "gray" },
                name: "Perfect calibration",
              },
            ]}
            layout={{
              title: "Elo Walk-Forward Calibration",
              xaxis: {
                title: { text: "Predicted home win rate" },
                tickformat: ".0%",
              },
              yaxis: {
                title: { text: "Actual home win rate" },
                tickformat: ".0%",
              },
            }}
          />
        </>
      ) : (
        <Info>Not enough completed matches for this training window.</Info>
      )}
    </Section>
  );
}
function useTeams() {
  const { data } = useApp();
  const options = [...data.teams]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((t) => ({ value: t.id, label: t.name }));
  const [home, setHome] = useState(options[0]?.value ?? ""),
    [selectedAway, setAway] = useState(options[1]?.value ?? "");
  const away =
    selectedAway === home
      ? options.find((t) => t.value !== home)?.value
      : selectedAway;
  const controls = (
    <div className="columns">
      <Select
        label="Home Team"
        value={home}
        onChange={setHome}
        options={options}
      />
      <Select
        label="Away Team"
        value={away}
        onChange={setAway}
        options={options.filter((o) => o.value !== home)}
      />
    </div>
  );
  return { home, away, controls };
}
function Override() {
  const { ratings, tname } = useApp(),
    { home, away, controls } = useTeams(),
    [ha, setHa] = useState(0),
    [aa, setAa] = useState(0);
  const p = winProbability(
    (ratings[home] ?? 1500) + ha,
    (ratings[away] ?? 1500) + aa,
  );
  return (
    <Section title="Manual Rating Override">
      {controls}
      <div className="columns">
        <Slider
          label={`${tname(home)} adjustment`}
          value={ha}
          onChange={setHa}
          min={-200}
          max={200}
          step={10}
        />
        <Slider
          label={`${tname(away)} adjustment`}
          value={aa}
          onChange={setAa}
          min={-200}
          max={200}
          step={10}
        />
      </div>
      <h3>Updated Predictions</h3>
      <Probability prediction={p} home={tname(home)} away={tname(away)} />
    </Section>
  );
}
function MatchSimulation() {
  const { data, ratings, tname } = useApp(),
    { home, away, controls } = useTeams();
  const [n, setN] = useState(5000),
    [result, setResult] = useState(null);
  const p = predictMatch(
    { id: "", home_team_id: home, away_team_id: away },
    data,
    ratings,
  );
  const visible =
    result?.homeId === home && result?.awayId === away && result?.n === n
      ? result
      : null;
  return (
    <Section title="Monte Carlo Match Simulation">
      {controls}
      <Slider
        label="Simulations"
        value={n}
        onChange={setN}
        min={1000}
        max={10000}
        step={1000}
      />
      {p.exp_home == null ? (
        <Info>
          Dixon-Coles parameters are required for both selected teams.
        </Info>
      ) : (
        <button
          className="action"
          onClick={() =>
            setResult({
              ...simulateMatch(p.exp_home, p.exp_away, n),
              homeId: home,
              awayId: away,
              n,
            })
          }
        >
          ▶ Run Simulation
        </button>
      )}
      {visible && (
        <>
          <Probability
            prediction={visible}
            home={tname(home)}
            away={tname(away)}
          />
          <div className="columns">
            <Chart
              data={[
                {
                  type: "histogram",
                  x: visible.totals,
                  marker: { color: "#5a9e10" },
                },
              ]}
              layout={{ title: "Total Points Distribution" }}
            />
            <Chart
              data={[
                {
                  type: "histogram",
                  x: visible.margins,
                  marker: { color: "#7c3aed" },
                },
              ]}
              layout={{ title: "Winning Margin Distribution" }}
            />
          </div>
        </>
      )}
    </Section>
  );
}
function BradleyTerry() {
  const { data, tname } = useApp(),
    { home, away, controls } = useTeams();
  const strengths = Object.fromEntries(
    data.bt.map((r) => [r.team_id, r.bt_strength]),
  );
  const p =
    strengths[home] != null && strengths[away] != null
      ? strengths[home] / (strengths[home] + strengths[away])
      : null;
  return (
    <>
      <Section title="Bradley-Terry Team Strengths">
        <Table
          rows={data.bt.map((r) => ({
            Team: tname(r.team_id),
            Strength: r.bt_strength,
          }))}
        />
      </Section>
      <Section title="Win Probability Calculator">
        {controls}
        {p == null ? (
          <Info>
            Bradley-Terry ratings are required for both selected teams.
          </Info>
        ) : (
          <div className="columns">
            <Metric label={tname(home)} value={pct(p)} />
            <Metric label={tname(away)} value={pct(1 - p)} />
          </div>
        )}
      </Section>
    </>
  );
}
function Season() {
  const { data, tname, ratings } = useApp(),
    [league, setLeague] = useState(data.leagues[0]?.id),
    [n, setN] = useState(10000),
    [result, setResult] = useState(null);
  const fixtures = data.matches.filter(
    (m) =>
      m.league_id === league &&
      m.status === "scheduled" &&
      new Date(m.kickoff_utc) >= Date.now(),
  );
  const visible =
    result?.league === league && result?.n === n ? result.rows : null;
  return (
    <Section title="Monte Carlo Season Simulation">
      <Select
        label="Competition"
        value={league}
        onChange={setLeague}
        options={data.leagues.map((l) => ({ value: l.id, label: l.name }))}
      />
      <Slider
        label="Simulations"
        value={n}
        onChange={setN}
        min={1000}
        max={20000}
        step={1000}
      />
      {fixtures.length ? (
        <>
          <p>
            {fixtures.length} remaining fixtures. Win = 4 points, draw = 2;
            bonus points are not simulated.
          </p>
          <button
            className="action"
            onClick={() =>
              setResult({
                league,
                n,
                rows: simulateSeason(
                  fixtures,
                  data.standings.filter((s) => s.league_id === league),
                  ratings,
                  n,
                ),
              })
            }
          >
            ▶ Run Season Simulation
          </button>
        </>
      ) : (
        <Info>No remaining fixtures for this competition.</Info>
      )}
      {visible && (
        <>
          <Bars
            labels={visible.map((r) => tname(r.team_id))}
            values={visible.map((r) => r.winner_prob)}
            title="Title Probability"
          />
          <Table
            rows={visible.map((r) => ({
              Team: tname(r.team_id),
              "Title %": pct(r.winner_prob),
              "Top 4 %": pct(r.top4_prob),
              ...Object.fromEntries(
                r.positions.map((v, i) => [`P${i + 1}`, pct(v)]),
              ),
            }))}
          />
        </>
      )}
    </Section>
  );
}
function Tournament() {
  const { data, ratings, tname } = useApp(),
    [league, setLeague] = useState(data.leagues[0]?.id),
    [size, setSize] = useState("8"),
    [n, setN] = useState(10000),
    [seeds, setSeeds] = useState(null),
    [result, setResult] = useState(null);
  const options = [...data.teams]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((t) => ({ value: t.id, label: t.name }));
  const defaults = data.teams
    .filter((t) => t.league_id === league)
    .sort((a, b) => (ratings[b.id] ?? 1500) - (ratings[a.id] ?? 1500))
    .slice(0, Number(size))
    .map((t) => t.id);
  const selected = seeds ?? defaults,
    valid =
      selected.length === Number(size) &&
      new Set(selected).size === selected.length;
  const signature = JSON.stringify([selected, n]),
    visible = result?.signature === signature ? result.rows : null;
  return (
    <>
      <Sidebar>
        <h2>Tournament Simulator</h2>
        <Select
          label="Competition"
          value={league}
          onChange={(v) => {
            setLeague(v);
            setSeeds(null);
          }}
          options={data.leagues.map((l) => ({ value: l.id, label: l.name }))}
        />
        <Select
          label="Bracket size"
          value={size}
          onChange={(v) => {
            setSize(v);
            setSeeds(null);
          }}
          options={["2", "4", "8", "16"].map((v) => ({
            value: v,
            label: `${v} teams`,
          }))}
        />
        <Slider
          label="Simulations"
          value={n}
          onChange={setN}
          min={1000}
          max={20000}
          step={1000}
        />
      </Sidebar>
      <Title caption="Monte Carlo knockout bracket simulation seeded by current Elo ratings.">
        🎯 Tournament Bracket Simulator
      </Title>
      <Section title="🏟️ Build Your Bracket">
        <p>
          Select exactly {size} teams (ordered = seeding: 1 vs 2, 3 vs 4, …)
        </p>
        <div className="seed-grid">
          {Array.from({ length: Number(size) }, (_, i) => (
            <Select
              key={i}
              label={`Seed ${i + 1}`}
              value={selected[i] ?? ""}
              onChange={(v) => {
                const next = [...selected];
                next[i] = v;
                setSeeds(next);
              }}
              options={[{ value: "", label: "Select a team" }, ...options]}
            />
          ))}
        </div>
        <Table
          rows={selected.filter(Boolean).map((id, i) => ({
            Seed: i + 1,
            Team: tname(id),
            "Elo Rating": Math.round(ratings[id] ?? 1500),
          }))}
        />
        {(!valid || selected.some((id) => !id)) && (
          <Info warning>Select exactly {size} distinct teams to continue.</Info>
        )}
      </Section>
      <hr />
      <button
        className="action"
        disabled={!valid || selected.some((id) => !id)}
        onClick={() =>
          setResult({ signature, rows: simulateBracket(selected, ratings, n) })
        }
      >
        ▶ Run {n.toLocaleString()} Simulations
      </button>
      {visible && (
        <>
          <div className="columns">
            <Section title="🏆 Title Probability">
              <Table
                rows={visible.map((r) => ({
                  Team: tname(r.team_id),
                  Rating: Math.round(ratings[r.team_id] ?? 1500),
                  "Win %": pct(r.title_prob),
                }))}
              />
            </Section>
            <Bars
              labels={visible.map((r) => tname(r.team_id))}
              values={visible.map((r) => r.title_prob)}
              title={`Tournament Win Probability — ${n.toLocaleString()} simulations`}
            />
          </div>
          <Section title="📊 Round-by-Round Progression">
            <Table
              rows={visible.map((r) => ({
                Team: tname(r.team_id),
                ...Object.fromEntries(
                  r.rounds.map((v, i) => [
                    i === r.rounds.length - 1
                      ? "Champion"
                      : `Round ${i + 1} Win`,
                    pct(v),
                  ]),
                ),
              }))}
            />
          </Section>
        </>
      )}
      <Footer />
    </>
  );
}
