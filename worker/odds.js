const leagues = {
  six_nations: "rugby-union-six-nations",
  premiership: "rugby-union-english-premiership",
  top14: "rugby-union-top-14",
  super_rugby: "rugby-union-super-rugby",
  urc: "rugby-union-united-rugby-championship",
  champions_cup: "rugby-union-european-rugby-champions-cup",
};
const normalize = (name) =>
  String(name)
    .toLowerCase()
    .replace(
      /\b(rugby|union|league|football|fc|rc|rl|club|sport|sports|county|city|united|town|athletic|athletico|nrl|afl)\b/g,
      "",
    )
    .replace(/[^a-z0-9 ]/g, "")
    .replace(/\s+/g, " ")
    .trim();
export function namesMatch(a, b) {
  const na = normalize(a),
    nb = normalize(b);
  if (!na || !nb) return false;
  if (na === nb || na.startsWith(nb) || nb.startsWith(na)) return true;
  return na.split(" ").some((w) => w.length >= 4 && nb.split(" ").includes(w));
}
const american = (d) =>
  d > 1 ? Math.round(d >= 2 ? (d - 1) * 100 : -100 / (d - 1)) : null;
export function marketRow(event, response) {
  const row = {
    match_id: event.match_id,
    scraped_at: new Date().toISOString(),
    source: "odds-api-io",
  };
  for (const bookmaker of ["DraftKings", "BetMGM BR"]) {
    const markets = response.bookmakers?.[bookmaker] ?? [];
    const market = (name) => markets.find((m) => m.name === name)?.odds ?? [];
    const ml = market("ML")[0];
    if (ml && row.home_ml == null) {
      row.home_ml = american(Number(ml.home));
      row.away_ml = american(Number(ml.away));
      row.bookmaker = bookmaker;
    }
    const spread = market("Spread").sort(
      (a, b) => Math.abs(Number(a.hdp)) - Math.abs(Number(b.hdp)),
    )[0];
    if (spread && row.spread_home == null) {
      row.spread_home = Number(spread.hdp);
      row.spread_home_odds = american(Number(spread.home));
    }
    const total = market("Totals")[0];
    if (total && row.total_line == null) {
      row.total_line = Number(total.hdp);
      row.total_over_odds = american(Number(total.over));
      row.total_under_odds = american(Number(total.under));
    }
  }
  return row;
}
export async function liveOdds(request, env, ctx) {
  if (!env.ODDS_API_IO_KEY)
    return Response.json({ odds: [], configured: false });
  const cacheKey = new Request(new URL("/api/odds", request.url));
  const cache = caches.default;
  const cached = await cache.match(cacheKey);
  if (cached) return cached;
  try {
    const asset = await env.ASSETS.fetch(
      new Request(new URL("/data/snapshot.json", request.url)),
    );
    const snapshot = await asset.json();
    const now = Date.now();
    const upcoming = snapshot.matches.filter(
      (m) =>
        m.status === "scheduled" &&
        new Date(m.kickoff_utc) >= now &&
        new Date(m.kickoff_utc) <= now + 14 * 86400000,
    );
    const names = Object.fromEntries(snapshot.teams.map((t) => [t.id, t.name]));
    const get = async (path, params) => {
      const url = new URL(`https://api.odds-api.io/v3/${path}`);
      url.search = new URLSearchParams({
        ...params,
        apiKey: env.ODDS_API_IO_KEY,
      }).toString();
      const response = await fetch(url, {
        signal: AbortSignal.timeout(10000),
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("Odds provider unavailable");
      return response.json();
    };
    const rows = [];
    // Only request active competitions and matched fixtures; cap requests per refresh.
    let budget = 12;
    for (const league of new Set(upcoming.map((m) => m.league_id))) {
      if (!leagues[league] || budget <= 0) continue;
      const events = await get("events", {
        sport: "rugby",
        league: leagues[league],
        status: "pending,live",
        limit: "50",
      });
      for (const event of Array.isArray(events) ? events : []) {
        if (budget <= 0) break;
        const match = upcoming.find(
          (m) =>
            m.league_id === league &&
            Math.abs(new Date(m.kickoff_utc) - new Date(event.date)) <=
              86400000 &&
            namesMatch(names[m.home_team_id], event.home) &&
            namesMatch(names[m.away_team_id], event.away),
        );
        if (!match) continue;
        budget--;
        const odds = await get("odds", {
          eventId: String(event.id),
          bookmakers: "DraftKings,BetMGM BR",
        });
        rows.push(marketRow({ match_id: match.id }, odds));
      }
    }
    const response = Response.json(
      { odds: rows, configured: true },
      { headers: { "Cache-Control": "public, max-age=3600" } },
    );
    ctx.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  } catch {
    const response = Response.json(
      { odds: [], unavailable: true },
      { headers: { "Cache-Control": "public, max-age=300" } },
    );
    ctx.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  }
}
