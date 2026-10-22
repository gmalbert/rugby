import { useEffect, useMemo, useState } from "react";
import {
  useApp,
  Sidebar,
  Title,
  Section,
  Info,
  Table,
  Select,
  MultiSelect,
  NumberInput,
  Metric,
  Form,
  Chart,
  Bars,
  Radar,
  Heatmap,
  Probability,
  columns,
} from "../ui.jsx";
import {
  aggregatePlayers,
  american,
  chrono,
  fmt,
  historicalTryProbability,
  implied,
  mean,
  outcome,
  pct,
  predictMatch,
  sum,
  teamMatches,
  teamStats,
} from "../analytics.js";
import Footer from "../Footer.jsx";

export default function Analytics({ page }) {
  if (page === "/League_Overview") return <League />;
  if (page === "/Team_Deep_Dive") return <Team />;
  if (page === "/Match_Analysis") return <Match />;
  return <Players compare={page === "/Player_Compare"} />;
}
function useLeague() {
  const { data } = useApp(),
    [league, setLeague] = useState(data.leagues[0]?.id ?? "");
  return [
    league,
    <Select
      label="Select League"
      value={league}
      onChange={setLeague}
      options={data.leagues.map((l) => ({ value: l.id, label: l.name }))}
    />,
  ];
}
function fixturesTable(matches, tname, leagueNames, odds) {
  return matches.map((m) => ({
    Date: new Date(m.kickoff_utc).toLocaleString("en-GB", { timeZone: "UTC" }),
    Home: tname(m.home_team_id),
    Away: tname(m.away_team_id),
    Venue: m.venue,
    Round: m.round,
    ...(odds?.[m.id]
      ? {
          "Home ML": american(odds[m.id].home_ml),
          "Away ML": american(odds[m.id].away_ml),
          "O/U": odds[m.id].total_line,
        }
      : {}),
  }));
}
function Results({ matches, id }) {
  const { tname } = useApp();
  return (
    <Table
      rows={matches.map((m) => ({
        Date: new Date(m.kickoff_utc).toLocaleDateString("en-GB", {
          timeZone: "UTC",
        }),
        Home: tname(m.home_team_id),
        Away: tname(m.away_team_id),
        Score: `${m.home_score} – ${m.away_score}`,
        ...(id ? { Result: outcome(m, id) } : {}),
      }))}
    />
  );
}
function League() {
  const { data, tname, leagueNames, odds } = useApp(),
    [league, control] = useLeague();
  const matches = data.matches.filter((m) => m.league_id === league),
    final = matches.filter((m) => m.status === "final");
  const standings = data.standings
    .filter((s) => s.league_id === league)
    .sort((a, b) => b.league_points - a.league_points);
  const teamIds = [
    ...new Set(final.flatMap((m) => [m.home_team_id, m.away_team_id])),
  ];
  const upcoming = matches
    .filter(
      (m) => m.status === "scheduled" && new Date(m.kickoff_utc) >= Date.now(),
    )
    .sort(chrono("kickoff_utc"));
  return (
    <>
      <Sidebar>
        <h3>League Overview</h3>
        {control}
      </Sidebar>
      <Title>📋 League Overview</Title>
      <h2>{leagueNames[league]}</h2>
      <Section title="🏅 Standings">
        <Table
          rows={standings.map((s, i) => ({
            "#": i + 1,
            Team: tname(s.team_id),
            P: s.played,
            W: s.won,
            L: s.lost,
            D: s.drawn,
            PF: s.points_for,
            PA: s.points_against,
            Diff: s.points_for - s.points_against,
            TF: s.tries_for,
            TA: s.tries_against,
            BP: s.bonus_points,
            Pts: s.league_points,
            Form: s.won > s.lost ? "↑" : s.won < s.lost ? "↓" : "→",
          }))}
        />
      </Section>
      <Section title="⚡ Attack Efficiency — Points per Game vs Tries per Game">
        <Chart
          data={[
            {
              type: "scatter",
              mode: "markers+text",
              x: standings.map((s) => s.tries_for / (s.played || 1)),
              y: standings.map((s) => s.points_for / (s.played || 1)),
              text: standings.map((s) => tname(s.team_id)),
              textposition: "top center",
              marker: { color: "#5a9e10", size: 10 },
            },
          ]}
          layout={{
            title: "Points per Game vs Tries per Game",
            xaxis: { title: { text: "TPG" } },
            yaxis: { title: { text: "PPG" } },
            shapes: [
              {
                type: "line",
                xref: "paper",
                x0: 0,
                x1: 1,
                y0: mean(
                  standings.map((s) => ({ v: s.points_for / (s.played || 1) })),
                  "v",
                ),
                y1: mean(
                  standings.map((s) => ({ v: s.points_for / (s.played || 1) })),
                  "v",
                ),
                line: { dash: "dot", color: "gray" },
              },
            ],
          }}
        />
      </Section>
      <Section title="🏠 Home vs Away Performance">
        <div className="columns">
          <Bars
            labels={teamIds.map(tname)}
            values={teamIds.map((id) =>
              mean(
                final.filter((m) => m.home_team_id === id),
                "home_score",
              ),
            )}
            title="Average Home Points"
          />
          <Bars
            labels={teamIds.map(tname)}
            values={teamIds.map((id) =>
              mean(
                final.filter((m) => m.away_team_id === id),
                "away_score",
              ),
            )}
            title="Average Away Points"
          />
        </div>
      </Section>
      <Section title="📅 Round-by-Round Results">
        {final.some((m) => m.round > 0) ? (
          <Table
            rows={[...final]
              .sort((a, b) => a.round - b.round)
              .map((m) => ({
                Round: m.round,
                "Home Team": tname(m.home_team_id),
                Score: `${m.home_score}–${m.away_score}`,
              }))}
          />
        ) : (
          <Info>
            Round results will appear here once matches are completed.
          </Info>
        )}
      </Section>
      <Section title="📆 Upcoming Fixtures">
        {upcoming.length ? (
          <Table rows={fixturesTable(upcoming, tname, leagueNames, odds)} />
        ) : (
          <Info>No upcoming fixtures for this league.</Info>
        )}
      </Section>
      {!!standings.length && (
        <Section title="📰 Season Snapshot">
          <Info>
            <b>{tname(standings[0].team_id)}</b> lead the table with{" "}
            {standings[0].league_points} points
            {standings[1]
              ? `, ${standings[0].league_points - standings[1].league_points} ahead of ${tname(standings[1].team_id)}`
              : ""}
            . Best attack:{" "}
            {tname(
              [...standings].sort(
                (a, b) =>
                  b.points_for / (b.played || 1) -
                  a.points_for / (a.played || 1),
              )[0].team_id,
            )}
            . Best defence:{" "}
            {tname(
              [...standings].sort(
                (a, b) =>
                  a.points_against / (a.played || 1) -
                  b.points_against / (b.played || 1),
              )[0].team_id,
            )}
            .
          </Info>
        </Section>
      )}
    </>
  );
}
function Team() {
  const { data, tname, leagueNames } = useApp();
  const options = [...data.teams]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((t) => ({ value: t.id, label: t.name }));
  const [id, setId] = useState(options[0]?.value ?? ""),
    [opp, setOpp] = useState(options[1]?.value ?? "");
  const opponent =
    opp === id ? options.find((t) => t.value !== id)?.value : opp;
  const rs = teamMatches(data.matches, id),
    stats = teamStats(data.matches, id),
    players = aggregatePlayers(data.players.filter((p) => p.team_id === id));
  const history = data.elo.filter((e) => e.team_id === id).sort(chrono("date"));
  const h2h = rs
    .filter((m) => m.home_team_id === opponent || m.away_team_id === opponent)
    .slice(-10)
    .reverse();
  const sums = data.players.filter((p) => p.team_id === id),
    n = stats.games || 1;
  return (
    <>
      <Sidebar>
        <Select
          label="Select Team"
          value={id}
          onChange={setId}
          options={options}
        />
        <Select
          label="H2H vs Opponent"
          value={opponent}
          onChange={setOpp}
          options={options.filter((t) => t.value !== id)}
        />
      </Sidebar>
      <Title>🔍 Team Deep Dive</Title>
      <h2>
        {tname(id)} ·{" "}
        {leagueNames[data.teams.find((t) => t.id === id)?.league_id]}
      </h2>
      <Section title="📊 Form Strip — Last 10 Results">
        <div className="columns">
          {rs
            .slice(-10)
            .reverse()
            .map((m) => (
              <div className="form-item" key={m.id}>
                <Form results={[outcome(m, id)]} />
                <small>
                  {tname(
                    m.home_team_id === id ? m.away_team_id : m.home_team_id,
                  )}{" "}
                  · {m.home_score}–{m.away_score}
                </small>
              </div>
            ))}
        </div>
        {!rs.length && <Info>No completed matches for this team.</Info>}
      </Section>
      <div className="columns">
        <Section title="⚡ Attack vs Defence Radar">
          <Radar
            labels={[
              "Tries Scored",
              "Tries Def",
              "Metres (×100)",
              "Linebreaks",
              "Tackles (×10)",
            ]}
            series={[
              {
                name: tname(id),
                values: [
                  stats.tries / n,
                  Math.max(10 - stats.tries_against / n, 0),
                  sum(sums, "metres_run") / n / 100,
                  sum(sums, "linebreaks") / n,
                  sum(sums, "tackles") / n / 10,
                ],
              },
            ]}
          />
        </Section>
        <Section title="📈 Elo Rating History">
          {history.length ? (
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
              layout={{
                title: `Elo Rating — ${tname(id)}`,
                yaxis: { title: { text: "Elo" } },
              }}
            />
          ) : (
            <Info>No Elo history yet.</Info>
          )}
        </Section>
      </div>
      <Section title="🎯 Scoring Breakdown">
        <Bars
          labels={["Try-derived points", "Penalties / Drops / Conversions"]}
          values={[
            stats.tries * 5,
            Math.max(0, stats.points - stats.tries * 5),
          ]}
          title="Season Points Breakdown"
        />
      </Section>
      <Section title="⭐ Key Players This Season">
        <div className="columns three">
          {[
            ["tries", "Top Try Scorers"],
            ["metres_run", "Top Metres Carriers"],
            ["tackles", "Top Tacklers"],
          ].map(([key, label]) => (
            <div key={key}>
              <h4>{label}</h4>
              <Table
                rows={[...players]
                  .sort((a, b) => b[key] - a[key])
                  .slice(0, 5)
                  .map((p) => ({ Player: p.player_name, [label]: p[key] }))}
              />
            </div>
          ))}
        </div>
      </Section>
      <Section title={`⚔️ Head-to-Head vs ${tname(opponent)}`}>
        {h2h.length ? (
          <Results matches={h2h} id={id} />
        ) : (
          <Info>No head-to-head meetings recorded.</Info>
        )}
      </Section>
      <Section title="🏟️ Venue Stats — Home vs Away Split">
        <Table
          rows={["Home", "Away"].map((side) => {
            const ms = rs.filter(
              (m) =>
                m[side === "Home" ? "home_team_id" : "away_team_id"] === id,
            );
            return {
              Venue: side,
              Games: ms.length,
              Wins: ms.filter((m) => outcome(m, id) === "W").length,
              "Avg PF": mean(ms, side === "Home" ? "home_score" : "away_score"),
              "Avg PA": mean(ms, side === "Home" ? "away_score" : "home_score"),
            };
          })}
        />
      </Section>
    </>
  );
}
function Players({ compare }) {
  const { data, leagues, tname } = useApp();
  const [positions, setPositions] = useState([]),
    [a, setA] = useState(""),
    [b, setB] = useState(""),
    [propId, setPropId] = useState(""),
    [odds, setOdds] = useState(150),
    [stat, setStat] = useState("tries");
  const allRows = data.players.filter(
    (p) => !leagues.length || leagues.includes(p.league_id),
  );
  const positionOptions = [
    ...new Set(allRows.map((p) => p.position).filter(Boolean)),
  ]
    .sort()
    .map((p) => ({ value: p, label: p }));
  const rows = allRows.filter(
    (p) => !positions.length || positions.includes(p.position),
  );
  const players = useMemo(() => aggregatePlayers(rows), [rows]);
  const key = (p) => `${p.player_id}|${p.team_id}|${p.position}`;
  const options = [...players]
    .sort((x, y) => x.player_name.localeCompare(y.player_name))
    .map((p) => ({
      value: key(p),
      label: `${p.player_name} · ${tname(p.team_id)}`,
    }));
  const pa = players.find((p) => key(p) === a) ?? players[0],
    pb = players.find((p) => key(p) === b) ?? players[1];
  const prop = players.find((p) => key(p) === propId) ?? pa;
  const historical = historicalTryProbability(prop?.rows ?? []);
  const stats = [
    "tries",
    "carries",
    "metres_run",
    "tackles",
    "missed_tackles",
    "linebreaks",
    "assists",
  ];
  const labels = {
    tries: "Tries",
    carries: "Carries",
    metres_run: "Metres",
    tackles: "Tackles",
    missed_tackles: "Missed Tackles",
    linebreaks: "Linebreaks",
    assists: "Assists",
  };
  const selectA = (
    <Select
      label={compare ? "🔵 Player A" : "Select Player"}
      value={pa ? key(pa) : ""}
      onChange={setA}
      options={options}
    />
  );
  return (
    <>
      <Sidebar>
        <MultiSelect
          label="Filter by Position"
          value={positions}
          onChange={setPositions}
          options={positionOptions}
        />
      </Sidebar>
      <Title
        caption={
          compare
            ? "Side-by-side radar comparison of any two players across all tracked stats."
            : undefined
        }
      >
        {compare
          ? "🔬 Player Comparison"
          : "👤 Player Stats & Try Scorer Props"}
      </Title>
      {!pa ? (
        <Info warning>No player stats available for the current filters.</Info>
      ) : compare && !pb ? (
        <Info>Not enough players for comparison with the current filters.</Info>
      ) : compare ? (
        <>
          <div className="columns">
            <div>
              {selectA}
              <h3>🔵 {pa.player_name}</h3>
              <PlayerMetrics p={pa} tname={tname} />
            </div>
            <div>
              <Select
                label="🔴 Player B"
                value={key(pb)}
                onChange={setB}
                options={options}
              />
              <h3>🔴 {pb.player_name}</h3>
              <PlayerMetrics p={pb} tname={tname} />
            </div>
          </div>
          <Section title="⚡ Radar Comparison (per-game averages)">
            <Radar
              labels={stats.map((s) => labels[s])}
              series={[pa, pb].map((p) => ({
                name: p.player_name,
                values: stats.map((s) => p[s] / p.games),
              }))}
            />
          </Section>
          <Section title="📊 Season Totals — Side by Side">
            <Select
              label="Statistic"
              value={stat}
              onChange={setStat}
              options={stats.map((s) => ({ value: s, label: labels[s] }))}
            />
            <Bars
              labels={[pa.player_name, pb.player_name]}
              values={[pa[stat], pb[stat]]}
              title={labels[stat]}
            />
          </Section>
          <Section title="📋 Full Stats Table">
            <Table
              rows={stats.map((s) => ({
                Stat: labels[s],
                [pa.player_name]: pa[s],
                [pb.player_name === pa.player_name
                  ? `${pb.player_name} (B)`
                  : pb.player_name]: pb[s],
              }))}
            />
          </Section>
          <Footer />
        </>
      ) : (
        <>
          <Section title="🏆 Try Scorer Rankings">
            <Table
              rows={players.map((p) => ({
                Player: p.player_name,
                Team: tname(p.team_id),
                Position: p.position,
                Tries: p.tries,
                Games: p.games,
                "T/Game": p.tpg,
                "Last 3": p.last3,
              }))}
            />
          </Section>
          <Section title="👤 Player Profile">
            {selectA}
            <PlayerMetrics p={pa} tname={tname} />
            <div className="columns">
              <Bars
                labels={pa.rows.map(
                  (p) => p.kickoff_utc?.slice(0, 10) || p.match_id,
                )}
                values={pa.rows.map((p) => p.tries)}
                title="Tries by Match"
              />
              <Chart
                data={[
                  {
                    type: "scatter",
                    mode: "lines+markers",
                    x: pa.rows.map((p) => p.kickoff_utc ?? p.match_id),
                    y: pa.rows.map((p) => p.minutes_played),
                  },
                ]}
                layout={{ title: "Minutes Played Trend" }}
              />
            </div>
          </Section>
          <Section title="💰 Prop Bet Analyzer">
            <div className="columns">
              <div>
                <Select
                  label="Player"
                  value={key(prop)}
                  onChange={setPropId}
                  options={options}
                />
                <NumberInput
                  label="DraftKings Odds (American, e.g. +150 or -120)"
                  value={odds}
                  onChange={setOdds}
                  min={-10000}
                  max={10000}
                  step={5}
                />
              </div>
              {Math.abs(odds) < 100 ? (
                <Info warning>
                  Enter American odds of +100 or greater, or −100 or less.
                </Info>
              ) : (
                <div>
                  <Metric
                    label="Model Probability"
                    value={pct(historical.probability)}
                  />
                  <p className="caption">
                    Based on {historical.scored}/{historical.games} games with a
                    try (smoothed prior: 1/5)
                  </p>
                  <Metric
                    label="DK Implied Probability"
                    value={pct(implied(odds))}
                  />
                  <Metric
                    label="Edge"
                    value={pct(historical.probability - implied(odds))}
                  />
                  <Metric
                    label="Expected Value (per $1)"
                    value={`$${(historical.probability * (odds > 0 ? odds / 100 : 100 / -odds) - (1 - historical.probability)).toFixed(2)}`}
                  />
                </div>
              )}
            </div>
          </Section>
          <Footer />
        </>
      )}
    </>
  );
}
function PlayerMetrics({ p, tname }) {
  return (
    <>
      <p>
        {tname(p.team_id)} · {p.position}
      </p>
      <div className="columns three">
        <Metric label="Season Tries" value={p.tries} />
        <Metric label="T/Game" value={fmt(p.tpg)} />
        <Metric label="Games" value={p.games} />
        <Metric label="Consistency" value={pct(p.consistency)} />
        <Metric label="Avg Minutes" value={fmt(p.avg_minutes)} />
      </div>
    </>
  );
}
function Match() {
  const { data, tname, ratings, odds, leagueNames } = useApp();
  const upcoming = data.matches
    .filter(
      (m) => m.status === "scheduled" && new Date(m.kickoff_utc) >= Date.now(),
    )
    .sort(chrono("kickoff_utc"));
  const [id, setId] = useState(upcoming[0]?.id ?? ""),
    m = upcoming.find((m) => m.id === id) ?? upcoming[0];
  if (!m)
    return (
      <>
        <Title>🔬 Match Analysis</Title>
        <Info>No upcoming fixtures available for analysis.</Info>
      </>
    );
  const p = predictMatch(m, data, ratings),
    home = tname(m.home_team_id),
    away = tname(m.away_team_id),
    line = odds[m.id];
  const h2h = data.matches
    .filter(
      (x) =>
        x.status === "final" &&
        [x.home_team_id, x.away_team_id].includes(m.home_team_id) &&
        [x.home_team_id, x.away_team_id].includes(m.away_team_id),
    )
    .sort(chrono("kickoff_utc"))
    .slice(-5)
    .reverse();
  const hs = teamStats(data.matches, m.home_team_id),
    as = teamStats(data.matches, m.away_team_id);
  const comparison = [
    ["Win %", pct(hs.wins / (hs.games || 1)), pct(as.wins / (as.games || 1))],
    ["Points / game", hs.points / (hs.games || 1), as.points / (as.games || 1)],
    ["Tries / game", hs.tries / (hs.games || 1), as.tries / (as.games || 1)],
    [
      "Tries conceded / game",
      hs.tries_against / (hs.games || 1),
      as.tries_against / (as.games || 1),
    ],
    ...["metres_run", "linebreaks", "tackles", "missed_tackles"].map((k) => [
      k.replaceAll("_", " "),
      sum(
        data.players.filter((p) => p.team_id === m.home_team_id),
        k,
      ) / (hs.games || 1),
      sum(
        data.players.filter((p) => p.team_id === m.away_team_id),
        k,
      ) / (as.games || 1),
    ]),
  ];
  return (
    <>
      <Sidebar>
        <Select
          label="Select Fixture"
          value={m.id}
          onChange={setId}
          options={upcoming.map((x) => ({
            value: x.id,
            label: `${tname(x.home_team_id)} vs ${tname(x.away_team_id)} (${x.kickoff_utc.slice(0, 10)})`,
          }))}
        />
      </Sidebar>
      <Title>🔬 Match Analysis</Title>
      <h2>
        {home} vs {away}
      </h2>
      <p className="caption">
        {leagueNames[m.league_id]} · {new Date(m.kickoff_utc).toUTCString()} ·{" "}
        {m.venue}
      </p>
      <div className="columns">
        <Section title="🎲 Win Probabilities">
          <Probability prediction={p} home={home} away={away} />
          <p className="caption">Model: {p.source}</p>
        </Section>
        {p.exp_home != null && (
          <Section title="🎯 Predicted Score">
            <div className="columns">
              <Metric label={home} value={fmt(p.exp_home)} />
              <Metric label={away} value={fmt(p.exp_away)} />
            </div>
            <Table
              rows={p.top.map((s) => ({
                Scoreline: `${s.home}–${s.away}`,
                Probability: pct(s.probability),
              }))}
            />
          </Section>
        )}
      </div>
      {p.matrix && (
        <Section title="📊 Scoreline Distribution">
          <Heatmap matrix={p.matrix} />
        </Section>
      )}
      <Section title="⚔️ Last 5 Meetings">
        {h2h.length ? (
          <Results matches={h2h} />
        ) : (
          <Info>No previous meetings recorded.</Info>
        )}
      </Section>
      <Section title="📏 Key Stats Comparison">
        <Table
          rows={comparison.map(([Stat, h, a]) => ({
            Stat,
            [home]: h,
            [away]: a,
          }))}
        />
      </Section>
      <Section title="🏃 Predicted Try Scorers">
        {data.try_predictions?.[m.id]?.length ? (
          <Table
            rows={data.try_predictions[m.id].map((s) => ({
              Team: tname(s.team_id),
              Player: s.player_name,
              Prob: pct(s.prob),
            }))}
          />
        ) : (
          <Info>
            Try scorer predictions require player stat data from completed
            matches.
          </Info>
        )}
      </Section>
      <Section title="💰 DraftKings Odds vs Model">
        {line ? (
          <Table
            rows={[
              [home, line.home_ml, p.home],
              [away, line.away_ml, p.away],
            ]
              .filter(([, ml]) => ml != null)
              .map(([Team, ml, prob]) => ({
                Team,
                "DK ML": american(ml),
                "Model Prob": pct(prob),
                "DK Implied": pct(implied(ml)),
                Edge: pct(prob - implied(ml)),
                Signal: prob > implied(ml) + 0.05 ? "✅ Back" : "🔴 Fade",
              }))}
          />
        ) : (
          <Info>No odds available for this fixture.</Info>
        )}
      </Section>
      <Weather match={m} />
      <Footer />
    </>
  );
}
function Weather({ match }) {
  const { data } = useApp(),
    [weather, setWeather] = useState(null),
    [failed, setFailed] = useState(false);
  const coords = data.venues?.[match.venue];
  useEffect(() => {
    setWeather(null);
    setFailed(false);
    if (!coords) return;
    const controller = new AbortController();
    const params = new URLSearchParams({
      latitude: coords[0],
      longitude: coords[1],
      hourly: "temperature_2m,precipitation,wind_speed_10m",
      forecast_days: "16",
      timezone: "UTC",
    });
    fetch(`https://api.open-meteo.com/v1/forecast?${params}`, {
      signal: controller.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then((json) => setWeather(json.hourly))
      .catch((e) => {
        if (e.name !== "AbortError") setFailed(true);
      });
    return () => controller.abort();
  }, [match.id, coords]);
  if (!coords) return null;
  const index =
    weather?.time.findIndex(
      (t) => t.slice(0, 13) === match.kickoff_utc.slice(0, 13),
    ) ?? -1;
  return (
    <Section title="🌦️ Venue Weather at Kickoff">
      {failed ? (
        <Info>Weather is temporarily unavailable.</Info>
      ) : !weather ? (
        <Info>Loading venue forecast…</Info>
      ) : index < 0 ? (
        <Info>Forecast will be available within 16 days of kickoff.</Info>
      ) : (
        <>
          <div className="columns three">
            <Metric
              label="Temperature"
              value={`${weather.temperature_2m[index]} °C`}
            />
            <Metric
              label="Wind"
              value={`${weather.wind_speed_10m[index]} km/h`}
            />
            <Metric
              label="Precipitation"
              value={`${weather.precipitation[index]} mm`}
            />
          </div>
          <p className="caption">Forecast: Open-Meteo · {match.venue}</p>
        </>
      )}
    </Section>
  );
}
