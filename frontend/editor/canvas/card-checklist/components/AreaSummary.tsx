// Souhrn oblasti pod jejím štítkem: kolik karet má pipeline, důkazy a předávky (pruh) a kolik čeká na člověka.
import type { areaSummary } from "@/editor/canvas/card-checklist/logic/card-checklist";
import "@/editor/canvas/card-checklist/styles/card-checklist.css";

export default function AreaSummary({ summary }: { summary: ReturnType<typeof areaSummary> }) {
  if (!summary.total) return null;
  return (
    <div className="area-summary" aria-label="Souhrn oblasti">
      <span className="area-summary__count">karty {summary.total}</span>
      {summary.bars.map((bar) => (
        <span key={bar.key} className="area-summary__bar" title={`${bar.label}: ${bar.value} z ${summary.total}`}>
          <span>{bar.label} {bar.value}/{summary.total}</span>
          <i><i style={{ width: `${Math.round((100 * bar.value) / summary.total)}%` }} /></i>
        </span>
      ))}
      {summary.waiting > 0 && <span className="area-summary__waiting">čeká na tebe {summary.waiting}</span>}
    </div>
  );
}
