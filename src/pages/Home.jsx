import { useEffect, useState } from "react";
import {
  useApp,
  Title,
  Section,
  Info,
  Table,
  Form,
  Metric,
  columns,
} from "../ui.jsx";
import {
  aggregatePlayers,
  american,
  chrono,
  group,
  outcome,
  teamMatches,
} from "../analytics.js";
import Footer from "../Footer.jsx";

export default function Home() {
  const { data, leagues, tname, leagueNames, odds } = useApp();
  const [live, setLive] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const r = await fetch("/api/live", { signal: controller.signal });
        if (!r.ok) return;
        const json = await r.json();
        setLive(json.events);
      } catch {
        /* Pipeline fallback below. */
      }
    };
    load();
    const interval = setInterval(load, 60000);
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, []);
  const matches = data.matches.filter(
    (m) => !leagues.length || leagues.includes(m.league_id),
  );
  const now = Date.now(),
    upcoming = matches
      .filter(
        (m) =>
          m.status === "scheduled" &&
          new Date(m.kickoff_utc) >= now &&
          new Date(m.kickoff_utc) <= now + 7 * 86400000,
      )
      .sort(chrono("kickoff_utc"));
  const scorers =
    (leagues.length === data.leagues.length && data.home_scorers) ||
    aggregatePlayers(
      data.players.filter(
        (p) => !leagues.length || leagues.includes(p.league_id),
      ),
    ).slice(0, 10);
  const liveMatches = live?.length
    ? live
    : matches
        .filter((m) => m.status === "live")
        .map((m) => ({
          ...m,
          home: tname(m.home_team_id),
          away: tname(m.away_team_id),
        }));
  const inView = [
    ...new Set(upcoming.flatMap((m) => [m.home_team_id, m.away_team_id])),
  ].sort();
  return (
    <>
      <Title caption="European rugby analytics & DraftKings betting intelligence">
        ScrumBet
      </Title>
      <div className="home-columns">
        <Section title="📅 This Week's Fixtures">
          {!upcoming.length && (
            <Info>No fixtures in the next 7 days for selected leagues.</Info>
          )}
          {Object.entries(
            group(upcoming, (m) => m.kickoff_utc.slice(0, 10)),
          ).map(([date, rows]) => (
            <div key={date} className="fixture-day">
              <p>
                <b>
                  {new Date(date + "T12:00Z").toLocaleDateString("en-GB", {
                    weekday: "long",
                    day: "2-digit",
                    month: "short",
                    timeZone: "UTC",
                  })}
                </b>
              </p>
              <Table
                rows={rows.map((m) => ({
                  League: leagueNames[m.league_id],
                  "KO (UTC)": new Date(m.kickoff_utc)
                    .toISOString()
                    .slice(11, 16),
                  Home: tname(m.home_team_id),
                  Away: tname(m.away_team_id),
                  Venue: m.venue,
                  ...(odds[m.id]?.home_ml != null
                    ? {
                        "Home ML": american(odds[m.id].home_ml),
                        "Away ML": american(odds[m.id].away_ml),
                      }
                    : {}),
                }))}
              />
            </div>
          ))}
        </Section>
        <div>
          <Section title="🔴 Live">
            {liveMatches.length ? (
              liveMatches.map((m, i) => (
                <Metric
                  key={m.id ?? i}
                  label={`${m.home} v ${m.away}`}
                  value={`${m.home_score} – ${m.away_score}`}
                  delta={m.minute}
                />
              ))
            ) : (
              <Info>No live matches.</Info>
            )}
          </Section>
          {upcoming.some((m) => odds[m.id]) && (
            <Section title="💰 DK Odds (Next 7 Days)">
              <Table
                rows={upcoming
                  .filter((m) => odds[m.id])
                  .map((m) => ({
                    Match: `${tname(m.home_team_id)} v ${tname(m.away_team_id)}`,
                    "H ML": american(odds[m.id].home_ml),
                    "A ML": american(odds[m.id].away_ml),
                    "O/U": odds[m.id].total_line,
                  }))}
              />
            </Section>
          )}
        </div>
        <Section title="🏆 Top Try Scorers">
          {scorers.length ? (
            <Table
              rows={scorers.map((p) => ({
                player_name: p.player_name,
                Team: tname(p.team_id),
                tries: p.tries,
              }))}
              columns={columns({
                player_name: "Player",
                Team: "Team",
                tries: "Tries",
              })}
            />
          ) : (
            <Info>Player stats load after first pipeline run.</Info>
          )}
        </Section>
      </div>
      <hr />
      <Section title="📊 Team Form — Last 5 Results">
        {inView.length ? (
          <div className="form-grid">
            {inView.map((id) => (
              <div key={id}>
                <b>{tname(id)}</b>
                <br />
                <Form
                  results={teamMatches(matches, id)
                    .slice(-5)
                    .reverse()
                    .map((m) => outcome(m, id))}
                />
              </div>
            ))}
          </div>
        ) : (
          <Info>Form data will appear here once fixtures are loaded.</Info>
        )}
      </Section>
      <Footer />
    </>
  );
}
