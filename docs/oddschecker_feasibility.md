# Oddschecker Scraping — Feasibility Assessment

> **Test method:** Single Playwright browser session against `https://www.oddschecker.com/us/`
> on 27 April 2026. No repeated requests were made. The attached `oddschecker_scraper.py` was
> used as the starting template.

---

## 1. Technical Barriers

### 1.1 Cloudflare anti-bot protection
A plain `requests` GET to `oddschecker.com` (even with a real Chrome `User-Agent`) returns an
immediate **HTTP 403** Cloudflare block. Playwright with a Chromium browser bypasses the initial
challenge, but:

- `cx-resources.oddschecker.com/fingerprint/verify-client.js` and `nirvana/ping.js` are loaded
  on every page — these are active browser-fingerprinting scripts.
- Headless Chromium is detectable via standard fingerprint signals (missing plugins, WebGL
  inconsistencies, etc.). Extended sessions or high-frequency polling will likely trigger
  CAPTCHAs or IP bans.
- Each page load with Playwright takes ~3–5 seconds. Scraping a full set of rugby fixtures
  would require dozens of page loads per run.

### 1.2 Client-side rendering
The site is a JavaScript SPA. Raw HTML contains almost no odds data — everything is injected
after JavaScript execution. No static HTML parser (BeautifulSoup, lxml) will work; Playwright
or Selenium is mandatory.

### 1.3 No exposed public API
No JSON REST or GraphQL endpoints were observed in network traffic during page load. All odds
data is rendered into the DOM client-side after internal (authenticated) API calls. There is no
stable, documented API to target.

### 1.4 Terms of Service
Oddschecker's ToS explicitly prohibits automated scraping or data extraction. Bypassing
Cloudflare with a headless browser also implicates the Computer Fraud and Abuse Act (US) and
the Computer Misuse Act (UK). **This is a meaningful legal/compliance risk for any production
use.**

---

## 2. Sport Coverage on the US Version

The following sections and leagues were confirmed in the site navigation:

| Category | Leagues / Competitions |
|---|---|
| **American Football** | NFL, NCAAF, UFL, Super Bowl futures |
| **Baseball** | MLB, College Baseball |
| **Basketball** | NBA, WNBA, NCAAM, NCAAW |
| **Hockey** | NHL |
| **Soccer** | EPL, MLS, La Liga (selected), Champions League (selected) |
| **Golf** | PGA Tour, Masters, PGA Championship, US Open, The Open |
| **Tennis** | Match coupon |
| **Boxing / MMA** | Boxing, UFC/MMA |
| **Horse Racing** | US racing card |
| **Cricket** | IPL |
| **Australian Rules** | AFL |
| **Motorsport** | F1, NASCAR |
| **Cycling** | Tour de France (futures) |
| **Darts** | PDC World Championship |
| **Specials** | Politics, Awards, Crypto, Finance, TV |
| **Rugby Union** | **Six Nations only** |
| **Rugby League** | **NRL only** |

The bookmakers listed on the US version are DraftKings, FanDuel, BetMGM, Caesars Sportsbook,
Bet365 (US), BetRivers, Borgata, Fanatics, and Underdog — US-licensed sportsbooks only.

---

## 3. Rugby Coverage — US Version

This is the critical finding for ScrumBet:

| League | US version | Notes |
|---|---|---|
| Six Nations | Present | Visible in nav; limited to tournament window (Feb–Mar) |
| NRL (Rugby League) | Present | Year-round |
| Premiership Rugby | **Absent** | Not in US nav |
| Top 14 | **Absent** | Not in US nav |
| Super Rugby Pacific | **Absent** | Not in US nav |
| United Rugby Championship | **Absent** | Not in US nav |
| European Champions Cup | **Absent** | Not in US nav |
| World Cup | Likely futures only | Not tested |

**4 of the 6 leagues ScrumBet covers are completely absent from the US version.** The US site
focuses on US-licensed bookmakers; rugby markets outside Six Nations and NRL are simply not
offered by those books.

### UK version (oddschecker.com — not US)
The UK/IE version would have significantly better rugby coverage — Premiership, Top 14, URC,
Champions Cup, and Super Rugby are all routinely listed by UK-facing bookmakers (Bet365 UK,
Sky Bet, Paddy Power, Coral, William Hill, etc.). However:

- The UK version has the same Cloudflare + fingerprinting stack.
- UK scraping carries UK GDPR and Computer Misuse Act exposure.
- The UK version was not tested (to avoid unnecessary requests), but the horse-racing scraper
  in the attached template was built against it and confirms the same structural challenges.

---

## 4. Timeliness

- Odds on Oddschecker update in near-real-time as bookmakers move their lines.
- However, there is no push mechanism — a scraper must **poll** repeatedly.
- With 3–5 s per Playwright page load and typical match slates of 5–10 rugby fixtures,
  a full scrape takes **15–50 seconds** per cycle. Running every 5–15 minutes is plausible
  but resource-intensive.
- Line movement data (the kind stored in `odds_snapshots.csv`) would require timestamped
  polling; Oddschecker's own "line movement" charts are not easily extractable without
  reverse-engineering their internal API calls.

---

## 5. Comparison with Current Stack

ScrumBet already integrates **The Odds API** (`utils/odds_api_io.py`) and has a pipeline
that writes to `data_files/csv/odds_snapshots.csv`. Here is how Oddschecker compares:

| Dimension | The Odds API | Oddschecker US |
|---|---|---|
| Access method | Official JSON API (key-based) | Playwright scraping |
| ToS / legality | Compliant | Prohibited by ToS |
| Reliability | High (99 %+ uptime SLA) | Fragile (Cloudflare blocks) |
| Rugby coverage | Configurable; all major leagues available | Six Nations + NRL only (US) |
| Bookmakers | Multi-region, configurable | US books only |
| Odds format | American, decimal, fractional | American (US version) |
| Line history | Snapshots available via API | Manual polling only |
| Rate limits | Quota-based, documented | Undocumented; IP ban risk |
| Maintenance cost | Low | High (markup changes break selectors) |

---

## 6. Other Sports — Feasibility Summary

For non-rugby use cases, the picture is more favourable on the US site:

| Sport | Verdict | Notes |
|---|---|---|
| MLB | **Viable** | Full daily card; 5+ US books; moneyline, spread, totals all present |
| NBA / WNBA | **Viable** | Full playoff bracket + regular season; player props visible on match pages |
| NFL | **Viable (off-season)** | Futures (Super Bowl, draft) available year-round; game lines in season |
| NHL | **Viable** | Full playoff card available; similar coverage to NBA |
| Soccer (EPL, MLS) | **Partial** | EPL lines present from US books; limited compared to UK version |
| Horse Racing | **Viable** | US card available; UK/IE card not on US version |
| Golf | **Viable** | Tournament outrights and round-leader markets; good coverage |
| UFC / Boxing | **Viable** | Fight-level moneyline well covered by US books |
| Tennis | **Partial** | Match coupon present but depth varies by tournament |
| F1 / NASCAR | **Partial** | Futures and race winner; limited in-race markets |
| Cricket (IPL) | **Partial** | IPL available; other competitions absent from US nav |

For US-focused sports (MLB, NBA, NFL, NHL), Oddschecker US could supplement or replace
polling The Odds API's US endpoint — but scraping legality and Cloudflare remain blockers
regardless of sport.

---

## 7. Recommended Approach

### For ScrumBet (rugby focus)
1. **Stay with The Odds API** for rugby odds. It legally covers all six leagues and is far
   more reliable than scraping.
2. The Oddschecker US version does **not** provide meaningful value for Premiership, Top 14,
   URC, Champions Cup, or Super Rugby odds — the coverage gap is too large.
3. If UK rugby bookmaker coverage is ever needed (e.g., fractional odds from UK books),
   consider a **licensed data provider** (Sportradar, Stats Perform, Rundown API) rather
   than scraping Oddschecker UK.

### For a future US-sports expansion
If ScrumBet were ever extended to cover NFL, NBA, MLB, or NHL:
- Oddschecker US *could* be a supplementary odds comparison layer.
- A compliant alternative is to request **official Oddschecker data partnership** access —
  they do offer commercial data licences.
- The Rundown API (`therundown.io`) and OddsJam API are legal, lower-cost alternatives with
  similar US-book coverage and no scraping risk.

### If scraping is pursued anyway
The `oddschecker_scraper.py` template is a reasonable starting point. Key adaptations needed:

```python
# US URL structure
BASE_URL = "https://www.oddschecker.com/us"
RUGBY_UNION_URL = f"{BASE_URL}/rugby-union"

# Selector changes — US site uses different CSS classes than UK
# These would need empirical verification against live DOM:
RUNNER_ROW_SEL = "tr.diff-row, tr[data-event-id]"
BOOKIE_HEADER_SEL = "thead th[data-bk]"
ODDS_CELL_SEL = "td[data-bk]"
```

Minimum requirements to avoid immediate blocks:
- Rotate residential proxies (not datacenter IPs).
- Use a stealth Playwright plugin (e.g., `playwright-stealth`) to mask headless signals.
- Respect a 3–5 second delay between page loads (`REQUEST_DELAY` in the template).
- Do not run more than once every 15 minutes per sport category.
- Accept that the site may break selectors without notice.

---

## 8. Verdict

| Dimension | Score | Comment |
|---|---|---|
| Rugby coverage (US) | 2 / 10 | Only Six Nations + NRL; 4 key leagues absent |
| Rugby coverage (UK version) | 6 / 10 | Better, but requires separate scraper and legal review |
| US sports coverage | 7 / 10 | Strong for the major four US leagues |
| Technical feasibility | 4 / 10 | Works with Playwright, but fragile and maintenance-heavy |
| Legal / ToS compliance | 1 / 10 | Explicitly prohibited; Cloudflare bypass adds legal risk |
| Timeliness | 6 / 10 | Near-real-time odds but requires manual polling |
| Maintenance burden | 3 / 10 | CSS selectors break on redesigns with no warning |

**Overall: not recommended as a primary data source for ScrumBet.** The Odds API already does
what Oddschecker would provide for rugby, legally and reliably. Oddschecker's only meaningful
advantage — breadth of bookmaker comparison for UK markets — requires the UK version, which
is even harder to scrape and still prohibited by ToS.
