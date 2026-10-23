import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  american,
  implied,
  decimal,
  fairOdds,
  kelly,
  kellyStake,
  historicalTryProbability,
  winProbability,
  scoreDistribution,
  currentRatings,
  backtest,
  simulateBracket,
  simulateSeason,
  simulateMatch,
} from "../src/analytics.js";

const close = (a, b, tolerance = 1e-9) =>
  assert.ok(Math.abs(a - b) < tolerance, `${a} != ${b}`);
test("American odds and Kelly preserve the original odds math", () => {
  close(implied(-150), 0.6);
  close(implied(200), 1 / 3);
  close(decimal(-150), 5 / 3);
  close(decimal(200), 3);
  close(implied(fairOdds(0.7)), 0.7);
  close(implied(fairOdds(0.2)), 0.2);
  close(kelly(0.6, 100, 0.25), 0.05);
  assert.equal(kelly(0.3, -200), 0);
  assert.equal(american(null), "—");
  assert.equal(american(120), "+120");
  assert.equal(kellyStake(0.99, 200, 1000, 1), 50);
  assert.equal(kellyStake(0.1, -200, 1000), 0);
});
test("try props use the existing one-in-five smoothing prior", () => {
  close(historicalTryProbability([]).probability, 0.2);
  close(
    historicalTryProbability([{ match_id: "a", tries: 1 }]).probability,
    2 / 6,
  );
  close(
    historicalTryProbability([
      { match_id: "a", tries: 1 },
      { match_id: "a", tries: 1 },
      { match_id: "b", tries: 0 },
    ]).probability,
    2 / 7,
  );
});
test("Elo win probabilities match the Python reference", () => {
  const p = winProbability(1500, 1500);
  close(p.home, 0.5303960070844291);
  close(p.draw, 0.08213422064790465);
  close(p.home + p.draw + p.away, 1);
});
test("scoreline probabilities partition the Poisson matrix", () => {
  const p = scoreDistribution(24, 20, -0.02);
  close(p.home + p.draw + p.away, 1, 1e-8);
  assert.equal(p.matrix.length, 80);
  assert.equal(p.top.length, 5);
  assert.ok(p.home > p.away);
  assert.ok(p.top[0].probability >= p.top[1].probability);
});
test("exported Dixon-Coles predictions agree with the browser implementation", () => {
  const data = JSON.parse(
    readFileSync(new URL("../public/data/snapshot.json", import.meta.url)),
  );
  const predictions = data.predictions.filter((p) => p.dc_exp_home != null);
  assert.ok(predictions.length > 0, "No reference predictions were exported");
  for (const p of predictions) {
    const computed = scoreDistribution(
      p.dc_exp_home,
      p.dc_exp_away,
      data.dc_model.rho,
    );
    close(computed.home, p.dc_p_home, 1e-8);
    close(computed.draw, p.dc_p_draw, 1e-8);
    close(computed.away, p.dc_p_away, 1e-8);
  }
  assert.ok(data.matches.length);
  assert.ok(data.players.length);
  assert.ok(
    !readFileSync(
      new URL("../public/data/snapshot.json", import.meta.url),
      "utf8",
    ).includes("API_KEY"),
  );
});
test("ratings select the most recent entry regardless of input ordering", () => {
  assert.deepEqual(
    currentRatings([
      { team_id: "a", rating: 1600, date: "2026-02-01" },
      { team_id: "a", rating: 1500, date: "2026-01-01" },
    ]),
    { a: 1600 },
  );
});
test("walk-forward backtesting scores held-out matches before updating ratings", () => {
  const matches = Array.from({ length: 12 }, (_, i) => ({
    id: String(i),
    status: "final",
    home_team_id: "a",
    away_team_id: "b",
    home_score: 20,
    away_score: 10,
    kickoff_utc: `2026-01-${String(i + 1).padStart(2, "0")}`,
  }));
  const result = backtest(matches, 10);
  assert.equal(result.length, 2);
  assert.ok(result[0].p < result[1].p);
  assert.equal(result[0].actual, 1);
});
test("knockout title probabilities sum to one and are reproducible", () => {
  const seeds = ["a", "b", "c", "d"],
    ratings = { a: 1800, b: 1400, c: 1500, d: 1500 };
  const rows = simulateBracket(seeds, ratings, 2000);
  close(
    rows.reduce((s, r) => s + r.title_prob, 0),
    1,
  );
  assert.equal(rows[0].team_id, "a");
  assert.deepEqual(rows, simulateBracket(seeds, ratings, 2000));
  assert.throws(() => simulateBracket(["a", "a"], ratings));
  rows.forEach((r) => assert.ok(r.rounds[0] >= r.title_prob));
});
test("season and match simulations return complete probability distributions", () => {
  const fixtures = [{ home_team_id: "a", away_team_id: "b" }];
  const result = simulateSeason(
    fixtures,
    [{ team_id: "a", league_points: 100 }],
    {},
    1000,
  );
  assert.equal(result[0].team_id, "a");
  close(result[0].winner_prob, 1);
  result.forEach((r) =>
    close(
      r.positions.reduce((a, b) => a + b, 0),
      1,
    ),
  );
  const match = simulateMatch(24, 20, 1000);
  close(match.home + match.away + match.draw, 1);
  assert.equal(match.totals.length, 1000);
});
