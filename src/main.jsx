import React, {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { createRoot } from "react-dom/client";
import { AppContext, Info, MultiSelect } from "./ui.jsx";
import { currentRatings, chrono } from "./analytics.js";
import "./styles.css";

const Analytics = lazy(() => import("./pages/Analytics.jsx"));
const Home = lazy(() => import("./pages/Home.jsx"));
const Betting = lazy(() => import("./pages/Betting.jsx"));
const Models = lazy(() => import("./pages/Models.jsx"));
const navigation = [
  ["", [["/", "🏉", "Home"]]],
  [
    "Analytics",
    [
      ["/League_Overview", "🏆", "League Overview"],
      ["/Team_Deep_Dive", "📊", "Team Deep Dive"],
      ["/Player_Stats", "👟", "Player Stats"],
      ["/Match_Analysis", "🔍", "Match Analysis"],
      ["/Player_Compare", "🔬", "Player Compare"],
    ],
  ],
  [
    "Betting",
    [
      ["/Betting_Edge", "⚡", "Betting Edge"],
      ["/Line_Movement", "📉", "Line Movement"],
    ],
  ],
  [
    "Models",
    [
      ["/Model_Lab", "🧪", "Model Lab"],
      ["/Tournament_Sim", "🎯", "Tournament Sim"],
    ],
  ],
];
const paths = navigation.flatMap(([, entries]) => entries.map((e) => e[0]));
function App() {
  const [path, setPath] = useState(location.pathname.replace(/\/$/, "") || "/");
  const [data, setData] = useState(null),
    [palettes, setPalettes] = useState(null),
    [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false),
    [sidebar, setSidebar] = useState(null);
  const [collapsed, setCollapsed] = useState(false),
    [leagues, setLeagues] = useState(null);
  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const responses = await Promise.all(
        ["/data/snapshot.json", "/data/themes.json"].map((url) =>
          fetch(url, { cache: "no-cache" }),
        ),
      );
      if (responses.some((r) => !r.ok))
        throw new Error("The site data could not be loaded. Please try again.");
      const [snapshot, themes] = await Promise.all(
        responses.map((r) => r.json()),
      );
      setData(snapshot);
      setPalettes(themes);
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setRefreshing(false);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (refreshing || !data?.generated_at) return;
    const controller = new AbortController();
    fetch("/api/odds", { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((result) => {
        if (result?.odds?.length)
          setData((current) =>
            current ? { ...current, live_odds: result.odds } : current,
          );
      })
      .catch(() => {
        /* Exported odds remain available when the provider is offline. */
      });
    return () => controller.abort();
  }, [refreshing, data?.generated_at]);
  useEffect(() => {
    const change = () => setPath(location.pathname.replace(/\/$/, "") || "/");
    window.addEventListener("popstate", change);
    return () => window.removeEventListener("popstate", change);
  }, []);
  const themeName =
    new Date().getHours() >= 6 && new Date().getHours() < 20
      ? "Emerald Isle"
      : "Night (Dark)";
  const theme = palettes?.[themeName];
  useEffect(() => {
    if (theme)
      Object.entries(theme).forEach(([k, v]) =>
        document.documentElement.style.setProperty(
          `--${k.replaceAll("_", "-")}`,
          v,
        ),
      );
  }, [theme]);
  const derived = useMemo(() => {
    if (!data) return null;
    const names = Object.fromEntries(data.teams.map((t) => [t.id, t.name]));
    const leagueNames = Object.fromEntries(
      data.leagues.map((l) => [l.id, l.name]),
    );
    const ratings = currentRatings(data.elo);
    const odds = Object.fromEntries(
      [...data.odds, ...(data.live_odds ?? [])]
        .sort(chrono("scraped_at"))
        .map((o) => [o.match_id, o]),
    );
    return {
      names,
      leagueNames,
      ratings,
      odds,
      tname: (id) =>
        names[id] ??
        id?.split("-").slice(1).join(" ").replaceAll("-", " ") ??
        "—",
    };
  }, [data]);
  function navigate(e, to) {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    history.pushState({}, "", to);
    setPath(to);
    window.scrollTo(0, 0);
    if (window.innerWidth < 800) setCollapsed(true);
  }
  const selectedLeagues = leagues ?? data?.leagues.map((l) => l.id) ?? [];
  const context = useMemo(
    () =>
      data && theme
        ? { data, ...derived, theme, sidebar, leagues: selectedLeagues }
        : null,
    [data, derived, theme, sidebar, selectedLeagues],
  );
  let page =
    path === "/" ? (
      <Home />
    ) : ["/Betting_Edge", "/Line_Movement"].includes(path) ? (
      <Betting page={path} />
    ) : ["/Model_Lab", "/Tournament_Sim"].includes(path) ? (
      <Models page={path} />
    ) : (
      <Analytics page={path} />
    );
  if (!paths.includes(path))
    page = (
      <>
        <h1>Page not found</h1>
        <a href="/" onClick={(e) => navigate(e, "/")}>
          Return to Home
        </a>
      </>
    );
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className={`app ${collapsed ? "sidebar-collapsed" : ""}`}>
        <aside aria-label="Sidebar">
          <button
            className="collapse"
            onClick={() => setCollapsed(true)}
            aria-label="Collapse sidebar"
          >
            «
          </button>
          <nav aria-label="Main navigation">
            {navigation.map(([group, entries]) => (
              <div className="nav-group" key={group}>
                {group && <div className="nav-heading">{group}</div>}
                {entries.map(([url, icon, title]) => (
                  <a
                    key={url}
                    href={url}
                    onClick={(e) => navigate(e, url)}
                    aria-current={path === url ? "page" : undefined}
                  >
                    <span>{icon}</span>
                    {title}
                  </a>
                ))}
              </div>
            ))}
          </nav>
          <hr className="nav-divider" />
          <img className="brand" src="/logo.png" alt="ScrumBet" />
          <hr />
          <button className="primary" onClick={load} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "🔄 Refresh cache"}
          </button>
          <p className="caption sources">
            Data: ESPN API · RugbyPass · SofaScore · The Odds API
          </p>
          {data &&
            [
              "/",
              "/Player_Stats",
              "/Player_Compare",
              "/Betting_Edge",
              "/Line_Movement",
            ].includes(path) && (
              <MultiSelect
                label={path === "/" ? "Filter Leagues" : "Filter by League"}
                value={selectedLeagues}
                onChange={setLeagues}
                options={data.leagues.map((l) => ({
                  value: l.id,
                  label: l.name,
                }))}
              />
            )}
          <div ref={setSidebar} />
        </aside>
        <header className="top-bar">
          {collapsed && (
            <button
              onClick={() => setCollapsed(false)}
              aria-label="Expand sidebar"
            >
              »
            </button>
          )}
        </header>
        <main id="main" className={path === "/" ? "home-page" : ""}>
          {error && (
            <Info warning>
              {error} <button onClick={load}>Retry</button>
            </Info>
          )}
          {!context && !error && <p role="status">Loading ScrumBet…</p>}
          {context && (
            <AppContext value={context}>
              <Suspense fallback={<p role="status">Loading page…</p>}>
                <div key={path}>{page}</div>
              </Suspense>
            </AppContext>
          )}
        </main>
      </div>
    </>
  );
}
createRoot(document.getElementById("root")).render(<App />);
