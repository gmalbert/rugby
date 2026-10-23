import {
  createContext,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { fmt } from "./analytics.js";

export const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);
export function Sidebar({ children }) {
  const { sidebar } = useApp();
  return sidebar ? createPortal(children, sidebar) : null;
}
export function Info({ children, warning = false }) {
  return (
    <div className={`info ${warning ? "warning" : ""}`} role="status">
      {children}
    </div>
  );
}
export function Title({ children, caption }) {
  return (
    <>
      <h1>{children}</h1>
      {caption && <p className="caption page-caption">{caption}</p>}
    </>
  );
}
export function Section({ title, children }) {
  return (
    <section>
      <h3>{title}</h3>
      {children}
    </section>
  );
}
export function Select({ label, value, onChange, options }) {
  return (
    <label className="field">
      {label}
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => {
          const v = typeof o === "object" ? o.value : o;
          return (
            <option key={v} value={v}>
              {typeof o === "object" ? o.label : o}
            </option>
          );
        })}
      </select>
    </label>
  );
}
export function MultiSelect({
  label,
  value,
  onChange,
  options,
  compact = false,
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    const close = (event) => {
      if (!ref.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);
  const summary =
    value.length === options.length
      ? `All Leagues (${options.length})`
      : value.length === 0
        ? "No League Filter"
        : value.length === 1
          ? options.find((o) => o.value === value[0])?.label
          : `${value.length} Leagues Selected`;
  return (
    <div
      className="field multi"
      ref={ref}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          setOpen(false);
          ref.current?.querySelector(".multi-summary, .multi-toggle")?.focus();
        }
      }}
    >
      <span id={`${id}-label`}>{label}</span>
      {compact ? (
        <button
          type="button"
          className="multi-box multi-summary"
          aria-label={`${label}: ${summary}`}
          aria-expanded={open}
          aria-controls={`${id}-options`}
          onClick={() => setOpen(!open)}
        >
          <span>{summary}</span>
          <span aria-hidden="true">{open ? "⌃" : "⌄"}</span>
        </button>
      ) : (
        <div className="multi-box">
          <div className="chips">
            {value.map((v) => (
              <button
                type="button"
                key={v}
                onClick={() => onChange(value.filter((x) => x !== v))}
                aria-label={`Remove ${options.find((o) => o.value === v)?.label ?? v}`}
              >
                {options.find((o) => o.value === v)?.label ?? v}
                <span aria-hidden="true">×</span>
              </button>
            ))}
          </div>
          <button
            type="button"
            className="multi-toggle"
            onClick={() => setOpen(!open)}
            aria-label={`Choose ${label}`}
            aria-expanded={open}
          >
            ⌄
          </button>
        </div>
      )}
      {open && (
        <div
          className="multi-options"
          id={`${id}-options`}
          role="group"
          aria-labelledby={`${id}-label`}
        >
          <button
            onClick={() =>
              onChange(
                value.length === options.length
                  ? []
                  : options.map((o) => o.value),
              )
            }
          >
            {value.length === options.length ? "Clear all" : "Select all"}
          </button>
          {options.map((o) => (
            <label key={o.value}>
              <input
                type="checkbox"
                checked={value.includes(o.value)}
                onChange={() =>
                  onChange(
                    value.includes(o.value)
                      ? value.filter((v) => v !== o.value)
                      : [...value, o.value],
                  )
                }
              />
              {o.label}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
export function Slider({ label, value, onChange, min, max, step = 1 }) {
  return (
    <label className="field">
      {label}
      <output>{value.toLocaleString()}</output>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="range-labels">
        <small>{min.toLocaleString()}</small>
        <small>{max.toLocaleString()}</small>
      </span>
    </label>
  );
}
export function NumberInput({ label, value, onChange, min, max, step = 1 }) {
  return (
    <label className="field">
      {label}
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}
export function Metric({ label, value, delta }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {delta && <small>{delta}</small>}
    </div>
  );
}
export function Form({ results }) {
  return (
    <span className="form-badges">
      {results.length ? (
        results.map((r, i) => (
          <span key={i} className={`badge ${r}`}>
            {r}
          </span>
        ))
      ) : (
        <em>No data</em>
      )}
    </span>
  );
}
export function Table({
  rows,
  columns,
  maxHeight = 400,
  download = true,
  plain = false,
  showIndex = false,
}) {
  const [sort, setSort] = useState(null);
  const cols =
    columns ||
    (rows[0] ? Object.keys(rows[0]).map((k) => ({ key: k, label: k })) : []);
  if (!rows.length) return <Info>No data to display.</Info>;
  const sorted = sort
    ? [...rows].sort((a, b) => {
        const va = a[sort.key],
          vb = b[sort.key];
        return (
          (typeof va === "number" && typeof vb === "number"
            ? va - vb
            : String(va ?? "").localeCompare(String(vb ?? ""))) * sort.direction
        );
      })
    : rows;
  function csv() {
    const quote = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;
    const content = [
      cols.map((c) => quote(c.label)),
      ...sorted.map((r) => cols.map((c) => quote(r[c.key]))),
    ]
      .map((r) => r.join(","))
      .join("\r\n");
    const url = URL.createObjectURL(
      new Blob([content], { type: "text/csv;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "scrumbet.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className={`table-shell ${plain ? "plain" : ""}`}>
      <div className="table-actions">
        {download && (
          <button
            onClick={csv}
            aria-label="Download table as CSV"
            title="Download CSV"
          >
            ⇩
          </button>
        )}
      </div>
      <div className="table-scroll" style={{ maxHeight }}>
        <table>
          <thead>
            <tr>
              {showIndex && <th className="row-index" aria-label="Row" />}
              {cols.map((c) => (
                <th
                  key={c.key}
                  aria-sort={
                    sort?.key === c.key
                      ? sort.direction === 1
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  <button
                    onClick={() =>
                      setSort({
                        key: c.key,
                        direction: sort?.key === c.key ? -sort.direction : 1,
                      })
                    }
                  >
                    {c.label}
                    {sort?.key === c.key
                      ? sort.direction === 1
                        ? " ↑"
                        : " ↓"
                      : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr key={r._key ?? i} className={r._signal ?? ""}>
                {showIndex && (
                  <td className="row-index">{rows.indexOf(r) + 1}</td>
                )}
                {cols.map((c) => (
                  <td
                    key={c.key}
                    className={
                      typeof r[c.key] === "number" ? "numeric" : undefined
                    }
                  >
                    {c.render
                      ? c.render(r[c.key], r)
                      : typeof r[c.key] === "number"
                        ? fmt(r[c.key])
                        : (r[c.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
export const columns = (names) =>
  Object.entries(names).map(([key, label]) => ({ key, label }));
export function Chart({ data, layout = {}, height = 360 }) {
  const { theme } = useApp(),
    ref = useRef(null),
    [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false,
      plotly;
    const element = ref.current;
    import("plotly.js-dist-min")
      .then((module) => {
        if (cancelled) return;
        plotly = module.default;
        const axis = {
          gridcolor: theme.border,
          zerolinecolor: theme.border,
          automargin: true,
        };
        return plotly.react(
          element,
          data,
          {
            height,
            autosize: true,
            margin: { l: 0, r: 0, t: 40, b: 0 },
            paper_bgcolor: theme.main_bg,
            plot_bgcolor: theme.main_bg,
            font: {
              color: theme.text,
              family: "Source Sans 3, sans-serif",
              size: 14,
            },
            colorway: ["#5a9e10", "#7c3aed", "#22c55e", "#ef4444", "#f59e0b"],
            ...layout,
            ...(typeof layout.title === "string"
              ? { title: { text: layout.title, font: { size: 16 }, x: 0 } }
              : {}),
            xaxis: { ...axis, ...layout.xaxis },
            yaxis: { ...axis, ...layout.yaxis },
          },
          {
            responsive: true,
            displaylogo: false,
            modeBarButtonsToRemove: ["sendDataToCloud"],
          },
        );
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load chart. Please refresh.");
      });
    const observer = new ResizeObserver(() => {
      if (
        !cancelled &&
        plotly &&
        element?.data &&
        element.isConnected &&
        element.clientWidth &&
        element.clientHeight
      )
        plotly.Plots.resize(element).catch(() => {
          /* Navigation can detach the chart while Plotly's resize is pending. */
        });
    });
    if (element) observer.observe(element);
    return () => {
      cancelled = true;
      observer.disconnect();
      if (plotly && element) plotly.purge(element);
    };
  }, [data, layout, height, theme]);
  return error ? (
    <Info warning>{error}</Info>
  ) : (
    <div
      className="chart"
      ref={ref}
      style={{ minHeight: height }}
      aria-label={
        typeof layout.title === "string"
          ? layout.title
          : "Interactive analytics chart"
      }
    />
  );
}
export function Bars({ labels, values, title, horizontal = false }) {
  return (
    <Chart
      height={320}
      data={[
        {
          type: "bar",
          x: horizontal ? values : labels,
          y: horizontal ? labels : values,
          orientation: horizontal ? "h" : "v",
          marker: { color: "#5a9e10" },
        },
      ]}
      layout={{ title }}
    />
  );
}
export function Probability({ prediction, home, away }) {
  return (
    <Chart
      height={260}
      data={[
        {
          type: "bar",
          x: [home, "Draw", away],
          y: [prediction.home, prediction.draw, prediction.away],
          marker: { color: ["#5a9e10", "#6b7280", "#7c3aed"] },
          text: [prediction.home, prediction.draw, prediction.away].map(
            (p) => `${(p * 100).toFixed(1)}%`,
          ),
          textposition: "auto",
        },
      ]}
      layout={{
        margin: { l: 0, r: 0, t: 20, b: 0 },
        yaxis: { tickformat: ".0%", title: { text: "Probability (%)" } },
      }}
    />
  );
}
export function Radar({ labels, series }) {
  const { theme } = useApp();
  const max = Math.max(1, ...series.flatMap((s) => s.values));
  return (
    <Chart
      height={series.length > 1 ? 400 : 360}
      data={series.map((s, i) => ({
        type: "scatterpolar",
        r: [...s.values, s.values[0]],
        theta: [...labels, labels[0]],
        fill: "toself",
        name: s.name,
        line: { color: i ? "#7c3aed" : "#5a9e10" },
        opacity: 0.75,
      }))}
      layout={{
        showlegend: series.length > 1,
        margin: { l: 30, r: 30, t: 50, b: 30 },
        polar: {
          bgcolor: theme.main_bg,
          radialaxis: {
            visible: true,
            range: [0, max * 1.1],
            gridcolor: theme.border,
          },
          angularaxis: { gridcolor: theme.border },
        },
      }}
    />
  );
}
export function Heatmap({ matrix }) {
  return (
    <Chart
      height={420}
      data={[
        {
          type: "heatmap",
          z: matrix.slice(0, 41).map((r) => r.slice(0, 41)),
          colorscale: "Blues",
          hovertemplate: "Home %{y} – Away %{x}<br>%{z:.3%}<extra></extra>",
        },
      ]}
      layout={{
        margin: { l: 60, r: 20, t: 20, b: 60 },
        xaxis: { title: { text: "Away Score" } },
        yaxis: { title: { text: "Home Score" } },
      }}
    />
  );
}
