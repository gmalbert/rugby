# ScrumBet: Railway → Cloudflare

The production frontend is now React + Vite. A Cloudflare Worker serves the
built app, the public pipeline snapshot, and two small API endpoints. Railway
and a long-running Streamlit server are no longer required to serve the site.
The original Python app remains available for comparison.

Initial deployment: https://scrumbet.gmalbert.workers.dev (22 October 2026).

Custom domains connected on 23 October 2026:

- https://scrumbet.com
- https://scrum-bet.com
- https://scrum-bets.com
- https://scrumbets.com

These hostnames are declared in `wrangler.jsonc`; the `workers.dev` address
remains enabled. Cloudflare manages their DNS and HTTPS certificates.

## Local development

```sh
npm ci
npm run dev
```

Vite serves the frontend at the URL printed in the terminal. For the complete
Worker runtime, including live API endpoints:

```sh
npm run build
npx wrangler dev
```

Use Node 22 or newer. The committed public snapshot allows Node-only builds.
Vite alone uses the exported data when the Worker API is absent.

## Refresh the underlying data

```sh
pip install -r requirements.txt
python -m scripts.pipeline
python -m scripts.export_web_data
```

The exporter reads the same CSV/Parquet sources as the original app, normalizes
IDs and UTC timestamps, copies the exact theme palettes and logo, and exports
the existing Python Dixon-Coles and try scorer models' outputs. It caches model
fits by a hash of their inputs. Only explicitly selected public data is written
to `public/`; `.env` and credentials are never bundled.

Nightly Data Refresh runs at 03:00 UTC, exports the React snapshot, commits the
data, and calls the Cloudflare deployment workflow. Reloading the page fetches
the latest deployed snapshot; it does not start a new scrape.

## Deploy

```sh
npx wrangler login
npm test
npm run deploy
```

`wrangler.jsonc` defines the `scrumbet` Worker, its `dist` static asset directory,
SPA navigation fallback, and `/api/*` routing. A direct request to an existing
Streamlit page path, such as `/Player_Compare`, works after deployment.

For automated deployments, set these GitHub repository secrets:

| Secret | Purpose |
| --- | --- |
| `CLOUDFLARE_ACCOUNT_ID` | Account that owns the Worker |
| `CLOUDFLARE_API_TOKEN` | Token with account Workers Scripts Edit permission |
| `ODDS_API_KEY` | Existing nightly The Odds API integration |
| `ODDS_API_IO_KEY` | Existing nightly odds-api.io integration |

Pushes to `main` deploy source changes. The nightly workflow calls deployment
explicitly because pushes made with `GITHUB_TOKEN` do not trigger another push
workflow. Without Cloudflare secrets, CI tests/builds and reports that deployment
is skipped. Adding secrets requires a user-created API token; the local Wrangler
OAuth login is not copied into GitHub.

To enable the original on-demand odds fallback on the Worker, configure its
server-only secret:

```sh
npx wrangler secret put ODDS_API_IO_KEY
```

`GET /api/odds` matches upcoming fixtures to provider events and returns normalized
DraftKings/BetMGM markets. Responses are cached for one hour at each Cloudflare
location; failures are cached for five minutes. Each refresh requests only
active competitions and at most twelve matched event odds. Provider quotas
still apply across locations. The exported odds remain the fallback.

`GET /api/live` polls SofaScore with a 30-second cache; the browser refreshes it
once a minute. If SofaScore refuses the request, the UI falls back to pipeline
scores. Weather uses Open-Meteo, as in the Python app.

## Appearance and behavior

All ten pages retain the original navigation paths, headings, logo, branding,
theme colors, data tables, form badges, and Plotly charts. The default palette
is Emerald Isle from 06:00–20:00 in the browser's local time and Night (Dark)
otherwise. All twenty original palette definitions remain in the export.

Interactive simulations and Elo backtesting run in the browser. Dixon-Coles
fits and logistic try scorer predictions stay in Python and are exported.
The prop analyzer retains its 1/5 smoothing prior; betting Kelly stakes retain
the 5% bankroll cap. The original historical-edge tracking placeholder remains.

The data committed in this checkout is older than the migration date. Empty
upcoming-fixture panels reflect that data. Run the pipeline or nightly workflow
to refresh it; the UI does not invent current fixtures or bookmaker prices.

## Cut over the existing domain

1. Verify the Worker URL, navigation, live sources, and nightly deployment.
2. In Cloudflare, open Workers & Pages → scrumbet → Settings → Domains & Routes
   and add the existing custom domain.
3. Complete Cloudflare's DNS cutover and verify TLS and direct page navigation.
4. Remove the Railway deployment after the custom domain and data refresh work.

No Railway service or existing DNS record is deleted by this code migration.

## Cloudflare Pages alternative

`npm run deploy:pages` publishes `dist` as a static Pages site, using Pages'
default SPA routing. This serves exported data; the Worker API endpoints require the
recommended Workers deployment. Do not configure both deployments for the same
custom domain.

## Validation

```sh
npm test
npm run lint
npm run build
npx wrangler deploy --dry-run
```

Tests cover Elo agreement with Python, Dixon-Coles agreement with exported
Python probabilities, odds conversion, smoothed props, stake caps, walk-forward
evaluation, simulation probabilities, Worker API routing, and market mapping.
