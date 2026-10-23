export const num = (x) =>
  Number.isFinite(Number(x)) && x !== null ? Number(x) : 0;
export const sum = (rows, key) => rows.reduce((a, r) => a + num(r[key]), 0);
export const mean = (rows, key) =>
  rows.length ? sum(rows, key) / rows.length : 0;
export const pct = (x) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);
export const fmt = (x) =>
  x == null || !Number.isFinite(Number(x))
    ? "—"
    : Number(x).toLocaleString("en-US", { maximumFractionDigits: 2 });
export const american = (x) =>
  x == null ? "—" : `${x > 0 ? "+" : ""}${Math.round(x)}`;
export const implied = (o) =>
  !o ? null : o > 0 ? 100 / (o + 100) : -o / (-o + 100);
export const decimal = (o) => (!o ? null : o > 0 ? 1 + o / 100 : 1 + 100 / -o);
export const fairOdds = (p) =>
  p <= 0 || p >= 1
    ? null
    : p >= 0.5
      ? (-100 * p) / (1 - p)
      : (100 * (1 - p)) / p;
export const kelly = (p, odds, fraction = 0.25) => {
  const b = decimal(odds) - 1;
  return b > 0 ? Math.max(0, (b * p - (1 - p)) / b) * fraction : 0;
};
export const kellyStake = (p, odds, bankroll, fraction = 0.5) =>
  Math.round(
    Math.min(kelly(p, odds, fraction) * bankroll, bankroll * 0.05) * 100,
  ) / 100;
export function historicalTryProbability(rows) {
  const games = Object.values(group(rows, "match_id"));
  const scored = games.filter((rs) => sum(rs, "tries") >= 1).length;
  return {
    games: games.length,
    scored,
    probability: (scored + 1) / (games.length + 5),
  };
}
export function group(rows, key) {
  return Object.groupBy(rows, typeof key === "function" ? key : (r) => r[key]);
}
export const chrono = (key) => (a, b) => new Date(a[key]) - new Date(b[key]);
export const teamMatches = (matches, id) =>
  matches
    .filter(
      (m) =>
        m.status === "final" &&
        (m.home_team_id === id || m.away_team_id === id),
    )
    .sort(chrono("kickoff_utc"));
export function outcome(m, id) {
  const diff =
    (num(m.home_score) - num(m.away_score)) * (m.home_team_id === id ? 1 : -1);
  return diff > 0 ? "W" : diff < 0 ? "L" : "D";
}
export function winProbability(home = 1500, away = 1500, advantage = 50) {
  const raw = 1 / (1 + 10 ** ((away - home - advantage) / 400));
  const draw = Math.max(0.03, 0.1 - Math.abs(raw - 0.5) * 0.25);
  return {
    home: Math.max(0.01, raw - draw / 2),
    draw,
    away: Math.max(0.01, 1 - raw - draw / 2),
  };
}
export function currentRatings(elo) {
  return Object.fromEntries(
    [...elo].sort(chrono("date")).map((r) => [r.team_id, r.rating]),
  );
}
export function aggregatePlayers(rows) {
  return Object.values(
    group(rows, (r) => `${r.player_id}|${r.team_id}|${r.position}`),
  )
    .map((rs) => {
      const r = rs[0],
        games = new Set(rs.map((x) => x.match_id)).size;
      const stats = Object.fromEntries(
        [
          "tries",
          "assists",
          "carries",
          "metres_run",
          "tackles",
          "missed_tackles",
          "linebreaks",
          "minutes_played",
        ].map((k) => [k, sum(rs, k)]),
      );
      return {
        ...r,
        ...stats,
        games,
        tpg: stats.tries / games,
        consistency: rs.filter((x) => x.tries > 0).length / games,
        avg_minutes: stats.minutes_played / games,
        last3: sum([...rs].sort(chrono("kickoff_utc")).slice(-3), "tries"),
        rows: rs,
      };
    })
    .sort((a, b) => b.tries - a.tries);
}
function poissonSeries(mu, max = 80) {
  const result = [Math.exp(-mu)];
  for (let i = 1; i < max; i++) result.push((result[i - 1] * mu) / i);
  return result;
}
export function scoreDistribution(home, away, rho = 0) {
  const h = poissonSeries(home),
    a = poissonSeries(away);
  const matrix = h.map((ph, i) =>
    a.map((pa, j) => {
      const tau =
        i === 0 && j === 0
          ? 1 - home * away * rho
          : i === 0 && j === 1
            ? 1 + home * rho
            : i === 1 && j === 0
              ? 1 + away * rho
              : i === 1 && j === 1
                ? 1 - rho
                : 1;
      return ph * pa * tau;
    }),
  );
  const p = { home: 0, draw: 0, away: 0 },
    scores = [];
  matrix.forEach((row, i) =>
    row.forEach((v, j) => {
      p[i > j ? "home" : i < j ? "away" : "draw"] += v;
      scores.push({ home: i, away: j, probability: v });
    }),
  );
  return {
    ...p,
    exp_home: home,
    exp_away: away,
    matrix,
    top: scores.sort((a, b) => b.probability - a.probability).slice(0, 5),
  };
}
export function predictMatch(m, data, ratings) {
  const pre = data.predictions.find((p) => p.match_id === m.id);
  const model = data.dc_model,
    hp = model?.teams?.[m.home_team_id],
    ap = model?.teams?.[m.away_team_id];
  if (hp && ap) {
    return {
      ...scoreDistribution(
        Math.exp(hp.attack - ap.defence + model.home_adv),
        Math.exp(ap.attack - hp.defence),
        model.rho,
      ),
      source: "Dixon-Coles",
    };
  }
  const p = pre
    ? {
        home: pre.elo_home_prob ?? pre.elo_p_home,
        draw: pre.elo_draw_prob ?? pre.elo_p_draw,
        away: pre.elo_away_prob ?? pre.elo_p_away,
      }
    : winProbability(ratings[m.home_team_id], ratings[m.away_team_id]);
  return { ...p, source: "Elo" };
}
export function teamStats(matches, id) {
  const rs = teamMatches(matches, id);
  return {
    games: rs.length,
    wins: rs.filter((m) => outcome(m, id) === "W").length,
    points: rs.reduce(
      (s, m) => s + num(m[m.home_team_id === id ? "home_score" : "away_score"]),
      0,
    ),
    conceded: rs.reduce(
      (s, m) => s + num(m[m.home_team_id === id ? "away_score" : "home_score"]),
      0,
    ),
    tries: rs.reduce(
      (s, m) => s + num(m[m.home_team_id === id ? "home_tries" : "away_tries"]),
      0,
    ),
    tries_against: rs.reduce(
      (s, m) => s + num(m[m.home_team_id === id ? "away_tries" : "home_tries"]),
      0,
    ),
  };
}
export function backtest(matches, minimum = 30) {
  const ratings = {},
    results = [];
  matches
    .filter(
      (m) =>
        m.status === "final" && m.home_score != null && m.away_score != null,
    )
    .sort(chrono("kickoff_utc"))
    .forEach((m, i) => {
      const h = ratings[m.home_team_id] ?? 1500,
        a = ratings[m.away_team_id] ?? 1500;
      const p = winProbability(h, a),
        diff = m.home_score - m.away_score,
        actual = diff > 0 ? 1 : diff < 0 ? 0 : 0.5;
      if (i >= minimum)
        results.push({
          p: p.home,
          actual: diff > 0 ? 1 : 0,
          correct: p.home > p.away === diff > 0,
          date: m.kickoff_utc,
        });
      const expected = 1 / (1 + 10 ** ((a - h - 50) / 400));
      const k = 32 * (diff ? Math.log(Math.abs(diff) + 1) + 1 : 1);
      ratings[m.home_team_id] = h + k * (actual - expected);
      ratings[m.away_team_id] = a + k * (expected - actual);
    });
  return results;
}
// Deterministic PRNG keeps results reproducible across filter changes and tests.
export function random(seed = 42) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export function simulateBracket(seeds, ratings, n = 10000) {
  if (
    ![2, 4, 8, 16].includes(seeds.length) ||
    new Set(seeds).size !== seeds.length
  )
    throw new Error("Select 2, 4, 8 or 16 distinct teams.");
  const rng = random(),
    rounds = Math.log2(seeds.length),
    counts = Object.fromEntries(seeds.map((t) => [t, Array(rounds).fill(0)]));
  for (let s = 0; s < n; s++) {
    let teams = [...seeds];
    for (let r = 0; teams.length > 1; r++) {
      const next = [];
      for (let i = 0; i < teams.length; i += 2) {
        const winner =
          rng() < winProbability(ratings[teams[i]], ratings[teams[i + 1]]).home
            ? teams[i]
            : teams[i + 1];
        counts[winner][r]++;
        next.push(winner);
      }
      teams = next;
    }
  }
  return seeds
    .map((t) => ({
      team_id: t,
      rounds: counts[t].map((v) => v / n),
      title_prob: counts[t][rounds - 1] / n,
    }))
    .sort((a, b) => b.title_prob - a.title_prob);
}
export function simulateSeason(fixtures, table, ratings, n = 10000) {
  const teams = [
    ...new Set(fixtures.flatMap((m) => [m.home_team_id, m.away_team_id])),
  ].sort();
  if (!teams.length) return [];
  const rng = random(),
    base = Object.fromEntries(
      table.map((t) => [t.team_id, num(t.league_points)]),
    );
  const counts = Object.fromEntries(
    teams.map((t) => [t, Array(teams.length).fill(0)]),
  );
  const probs = fixtures.map((m) =>
    winProbability(ratings[m.home_team_id], ratings[m.away_team_id]),
  );
  for (let i = 0; i < n; i++) {
    const pts = Object.fromEntries(teams.map((t) => [t, base[t] ?? 0]));
    fixtures.forEach((m, j) => {
      const r = rng();
      if (r < probs[j].home) pts[m.home_team_id] += 4;
      else if (r > 1 - probs[j].away) pts[m.away_team_id] += 4;
      else {
        pts[m.home_team_id] += 2;
        pts[m.away_team_id] += 2;
      }
    });
    [...teams]
      .sort((a, b) => pts[b] - pts[a])
      .forEach((t, pos) => counts[t][pos]++);
  }
  return teams
    .map((t) => ({
      team_id: t,
      winner_prob: counts[t][0] / n,
      top4_prob: counts[t].slice(0, 4).reduce((a, b) => a + b, 0) / n,
      positions: counts[t].map((v) => v / n),
    }))
    .sort((a, b) => b.winner_prob - a.winner_prob);
}
export function simulateMatch(home, away, n = 5000) {
  const rng = random(),
    drawPoisson = (mu) => {
      let p = 1,
        k = 0;
      do {
        k++;
        p *= rng();
      } while (p > Math.exp(-mu));
      return k - 1;
    };
  const totals = [],
    margins = [],
    wins = { home: 0, draw: 0, away: 0 };
  for (let i = 0; i < n; i++) {
    const h = drawPoisson(home),
      a = drawPoisson(away);
    totals.push(h + a);
    margins.push(h - a);
    wins[h > a ? "home" : h < a ? "away" : "draw"]++;
  }
  return {
    totals,
    margins,
    ...Object.fromEntries(Object.entries(wins).map(([k, v]) => [k, v / n])),
  };
}
