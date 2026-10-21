import { useState } from "react";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { evalExportUrl, evalsUrl, metricsUrl, metricsView, parseEvalCount, parseReviewMetrics, WINDOWS, type MetricsWindow } from "../logic/review-metrics";
import MetricBars from "./MetricBars";
import MetricTiles from "./MetricTiles";
import "../styles/oporahub-review-metrics.css";

const WINDOW_LABEL: Record<MetricsWindow, string> = { "7d": "7 dní", "30d": "30 dní", "90d": "90 dní", all: "vše" };

/** Metriky review: nálezy, šum, kola, lidský čas na PR a pojistky (reverty, incidenty) plus eval sada. */
export default function ReviewMetrics({ project, workspace }: { project: string; workspace: string }) {
  const [span, setSpan] = useState<MetricsWindow>("30d");
  const ready = !!project && !!workspace;
  const metrics = useHubRead(ready ? metricsUrl(project, workspace, span) : null, parseReviewMetrics);
  const evals = useHubRead(ready ? evalsUrl(project, workspace) : null, parseEvalCount);
  const view = metrics.data ? metricsView(metrics.data) : null;
  return <div className="oporahub-review-metrics" data-oh-view="review-metrics" data-oh-window={span}>
    <JsonMirror id="oh-review-metrics" value={{ metrics: metrics.data, evalCases: evals.data }} />
    <header className="oporahub-review-metrics__head">
      <h3 className="oporahub-review-metrics__title">Metriky review</h3>
      <label className="oporahub-review-metrics__window">Okno
        <select value={span} onChange={event => setSpan(event.target.value as MetricsWindow)}>
          {WINDOWS.map(item => <option key={item} value={item}>{WINDOW_LABEL[item]}</option>)}
        </select>
      </label>
      {view && <span className="oporahub-review-metrics__note" data-oh-metric="prsReviewed" data-oh-value={view.prsReviewed}>
        {view.prsReviewed} PR s review{view.truncated ? " · řádky PR zkráceny na 200" : ""}</span>}
    </header>
    {metrics.error && <p className="oporahub-review-metrics__error" role="alert">{metrics.error}</p>}
    {!view && !metrics.error && <p className="oporahub-review-metrics__note" role="status">Načítám metriky…</p>}
    {view && <>
      <MetricTiles title="Jak review funguje" tiles={view.tiles} />
      <div className="oporahub-review-metrics__charts">
        <MetricBars title="Nálezy podle závažnosti" bars={view.severity} />
        <MetricBars title="Co se s nálezy stalo" bars={view.outcomes} />
      </div>
      <MetricTiles title="Pojistky (guardrails)" tiles={view.guardrails} />
    </>}
    <section className="oporahub-review-metrics__evals" data-oh-metric="evalCases" data-oh-value={evals.data ?? ""}>
      <span><b>Eval sada:</b> {evals.data === null ? evals.error ? "nedostupná" : "načítám…" : `${evals.data} případů (reverty a incidenty)`}</span>
      {ready && <a className="oporahub-review-metrics__link" href={evalExportUrl(project, workspace)} download>Stáhnout export.jsonl</a>}
    </section>
  </div>;
}
