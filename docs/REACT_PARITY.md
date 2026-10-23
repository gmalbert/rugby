# Streamlit to React parity check — 23 October 2026

The repository already contained the React/Vite port and Cloudflare Worker.
This pass compared the running Python reference with the React application,
then verified the production bundle in Wrangler's local Worker runtime.

## Corrections

- Match Streamlit's 138px content start on all desktop pages, header spacing,
  sidebar section headings, and active navigation colors.
- Match native dataframe header/cell colors, font size, grid lines, numeric
  alignment, and the standings/player rankings' row index. Sorting preserves
  the original index.
- Restore the League Overview, Team Deep Dive, and Model Lab footers.
- Restore the inline team form strip and show scores from the selected team's
  perspective, including away games.
- Deduplicate team/player selector labels and select the first two distinct
  alphabetical player names by default.
- Restore the player profile's four metrics, tries-by-round bar chart,
  minutes-played bar chart, consistency text, and section dividers.
- Restore comparison metrics, metres-per-game scaling by ten, and both total
  and per-game comparison table columns.
- Match shared chart margins, bar/probability/heatmap heights, probability
  colors, and the blue scoreline heatmap. Restore both efficiency quadrant lines.
- Ignore pending chart resize work after navigation detaches its element.

## Verification

- `npm test`: 14 analytics and Worker tests passed.
- `npm run lint` and `npm run build`: passed.
- `wrangler deploy --dry-run`: Worker and assets packaged successfully.
- Local Worker HTTP checks: all ten direct page paths returned HTML with status
  200; the snapshot and logo returned their correct content types; an unknown
  `/api/` path returned 404.
- Browser checks: all ten pages rendered; all seven Model Lab tabs rendered;
  a four-team, 10,000-trial tournament simulation produced title probabilities
  and round progression with no browser errors in the production preview.
- At a 1280×720 viewport, both applications placed the home title at x=380,
  y=138 and its three section headings at y=265.1875. League Overview's title,
  league heading, and standings heading also match their reference positions.

## Limits

This is a visual and interaction parity pass, not an exhaustive pixel comparison
of every page, theme, viewport, or data state. React uses HTML tables instead of
Streamlit's canvas grid; native dataframe search, column controls, and fullscreen
tools are not replicated. Reloading the page loads the deployed snapshot instead of
starting Python scraping/model fitting.

The snapshot was exported on 22 October 2026, but its latest fixture is dated
6 June 2026. Upcoming-match analysis, live bookmaker rows, and weather cannot be
fully exercised with that snapshot. Refresh the Python pipeline and export to
validate those populated states. Python fitting and scraping remain in the
existing scheduled GitHub Actions workflow; they do not run inside the Worker.

## Annotation refinements

The sidebar refresh button and data-source credits were removed following the
browser review. League filters now use a collapsed selection summary with an
expandable checkbox menu, outside-click dismissal, and Escape-key dismissal.
Standings use full title-case column labels.

Tournament Sim remains available: computation runs in the visitor's browser
only after clicking Run, without simulation requests to Cloudflare. A local
Node benchmark of ten runs at 20,000 simulations measured median times of
9.4ms for eight teams and 19.1ms for sixteen teams (maximum 27.5ms).
These measurements describe computation on this machine, not chart rendering
or performance on every visitor's device.
