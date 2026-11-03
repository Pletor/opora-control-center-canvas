import type { HeartPipelineSummary } from "../logic/heart-pipeline";
import "../styles/heart-pipeline.css";

/** Část „Pracovní workflow a pipeline srdce“ pod nastavením projektu: co srdce je, živý souhrn jeho workflow a vstup
 * na jeho vlastní plátno. Data i otevření drží rodič (`ProjectHome` → App); dílek jen zobrazuje a hlásí klik. */
export default function HeartPipelineCard({ summary, loading, error, onOpen }: {
  summary: HeartPipelineSummary | null; loading: boolean; error: string; onOpen: () => void;
}) {
  return <section className="heart-pipeline" aria-label="Pracovní workflow a pipeline srdce" data-testid="heart-pipeline">
    <div className="heart-pipeline__text">
      <h2 className="heart-pipeline__title">Pracovní workflow a pipeline srdce</h2>
      <p className="heart-pipeline__lead">Srdce je LLM, které projekt řídí: čte záměr, plánuje karty a zadává práci dělníkům. Jeho workflow má vlastní plátno mimo architekturu projektu.</p>
      <p className="heart-pipeline__facts" role="status">
        {summary ? <>
          <span className="heart-pipeline__fact"><b>{summary.name}</b> · {summary.scope}</span>
          <span className="heart-pipeline__fact">aktivní verze <b>{summary.active}</b></span>
          <span className="heart-pipeline__fact"><b>{summary.runs}</b> běhů</span>
          <span className={summary.stalls ? "heart-pipeline__fact heart-pipeline__fact--stalled" : "heart-pipeline__fact"}><b>{summary.stalls}</b> prostojů</span>
        </> : loading ? "Načítám srdce projektu…" : error || "Projekt zatím nemá workflow srdce (kind heart)."}
      </p>
    </div>
    <button type="button" className="primary heart-pipeline__open" data-testid="heart-pipeline-open" onClick={onOpen}>Otevřít canvas srdce</button>
  </section>;
}
