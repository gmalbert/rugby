import test from "node:test";
import assert from "node:assert/strict";
import worker from "../worker/index.js";
import { marketRow, namesMatch } from "../worker/odds.js";

test("unknown API routes return JSON 404 instead of the SPA", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/missing"),
    {},
  );
  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), { error: "Not found" });
});
test("live endpoints reject writes", async () => {
  for (const path of ["live", "odds"]) {
    const response = await worker.fetch(
      new Request(`https://example.com/api/${path}`, { method: "POST" }),
      {},
    );
    assert.equal(response.status, 405);
  }
});
test("ordinary page requests are passed to Cloudflare assets", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/League_Overview"),
    { ASSETS: { fetch: () => new Response("SPA") } },
  );
  assert.equal(await response.text(), "SPA");
});
test("unconfigured odds endpoint exposes no credentials and allows CSV fallback", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/odds"),
    {},
  );
  assert.deepEqual(await response.json(), { odds: [], configured: false });
});
test("bookmaker markets normalize into the existing CSV schema", () => {
  const row = marketRow(
    { match_id: "abc" },
    {
      bookmakers: {
        DraftKings: [
          { name: "ML", odds: [{ home: "1.5", away: "3.0" }] },
          {
            name: "Spread",
            odds: [
              { hdp: "-9.5", home: "1.91" },
              { hdp: "-3.5", home: "1.91" },
            ],
          },
          {
            name: "Totals",
            odds: [{ hdp: "45.5", over: "1.91", under: "1.91" }],
          },
        ],
      },
    },
  );
  assert.equal(row.match_id, "abc");
  assert.equal(row.home_ml, -200);
  assert.equal(row.away_ml, 200);
  assert.equal(row.spread_home, -3.5);
  assert.equal(row.total_line, 45.5);
  assert.equal(row.bookmaker, "DraftKings");
  assert.ok(namesMatch("Leinster Rugby", "Leinster"));
  assert.ok(!namesMatch("", "Ireland"));
});
