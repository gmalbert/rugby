import { liveOdds } from "./odds.js";
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/api/odds") {
      if (request.method !== "GET")
        return new Response("Method not allowed", { status: 405 });
      return liveOdds(request, env, ctx);
    }
    if (url.pathname === "/api/live") {
      if (request.method !== "GET")
        return new Response("Method not allowed", { status: 405 });
      try {
        const response = await fetch(
          "https://api.sofascore.com/api/v1/sport/rugby-union/scheduled-events/live",
          {
            headers: { Accept: "application/json" },
            signal: AbortSignal.timeout(8000),
            cf: { cacheTtl: 30, cacheEverything: true },
          },
        );
        if (!response.ok) throw new Error("Live source unavailable");
        const data = await response.json();
        return Response.json(
          {
            events: (data.events || []).map((e) => ({
              id: e.id,
              home: e.homeTeam?.name,
              away: e.awayTeam?.name,
              home_score: e.homeScore?.current ?? 0,
              away_score: e.awayScore?.current ?? 0,
              minute: e.status?.description || "Live",
              competition: e.tournament?.name,
            })),
          },
          { headers: { "Cache-Control": "public, max-age=30" } },
        );
      } catch {
        return Response.json(
          { events: [], unavailable: true },
          { status: 503 },
        );
      }
    }
    if (url.pathname.startsWith("/api/"))
      return Response.json({ error: "Not found" }, { status: 404 });
    return env.ASSETS.fetch(request);
  },
};
