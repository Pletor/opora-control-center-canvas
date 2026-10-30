// Řádek souhrnu nad oblastmi: kolik vstupů srdce ještě nepotvrdilo, kolik čeká na stanovisko a kolik bylo
// duplicit. Nenulové číslo je tučné, aby oko našlo, kde je práce.
import { summaryParts, type PlanSummary } from "../logic/intake-plan";

export default function IntakeSummary({ summary }: { summary: PlanSummary }) {
  return (
    <p className="intake-plan__summary" data-oh-intake-fresh={summary.fresh} data-oh-intake-pending={summary.pending}
      data-oh-intake-duplicates={summary.duplicates}>
      <span className="intake-plan__eyebrow">Vstupy</span>
      {summaryParts(summary).map(part => (
        <span key={part.key} className={"intake-plan__summary-part" + (part.value ? " intake-plan__summary-part--some" : "")}>{part.text}</span>
      ))}
      <small className="intake-plan__muted">z posledních {summary.entries}</small>
    </p>
  );
}
