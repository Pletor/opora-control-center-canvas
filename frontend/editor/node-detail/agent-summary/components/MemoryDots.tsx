// Pět teček = pět polí paměti karty. Vyplněné tečky stojí vždy první, takže se dá odhadnout „kolik“
// jedním pohledem bez čísla; číslo „N/5“ je volitelné, protože v hlavičce kapitoly překáží.
import { memoryTitle } from "@/editor/node-detail/agent-summary/logic/agent-summary";
import "@/editor/node-detail/agent-summary/styles/agent-summary.css";

const TOTAL = 5;

export default function MemoryDots({ filled, showCount = false }: { filled: number; showCount?: boolean }) {
  const count = Math.max(0, Math.min(TOTAL, Math.floor(filled)));
  return (
    <span className="agent-summary__dots" title={memoryTitle(count)} data-testid="memory-dots">
      {Array.from({ length: TOTAL }, (_, index) => (
        <i key={index} className={"agent-summary__dot" + (index < count ? " agent-summary__dot--filled" : "")} aria-hidden="true" />
      ))}
      {showCount ? <small className="agent-summary__dots-count">{count}/{TOTAL}</small> : <span className="agent-summary__sr">{count} z {TOTAL}</span>}
    </span>
  );
}
