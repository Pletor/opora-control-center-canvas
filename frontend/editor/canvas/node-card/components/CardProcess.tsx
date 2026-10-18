// Proces karty pod hlavou: řada kuliček etap (barva = kdo, výplň = jak dopadl, kroužek = kde proces stojí)
// a za ní čtyři čtverečky dokladů Testy · Security · Review · Merge na pevných místech (docs/proces-karty.md).
// Dílek jen zobrazuje hotový pohled z `logic/card-process.ts` a `logic/card-proofs.ts`; nic neukládá.
import { DOT_TITLE, processSentence, type CardProcessView, type ProcessDot } from "../logic/card-process";
import type { ProofSlot } from "../logic/card-proofs";

function dotClass(dot: ProcessDot): string {
  return "node-card__stage"
    + " node-card__stage--kind-" + dot.kind
    + (dot.kind === "critic" && dot.lens ? " node-card__stage--lens-" + dot.lens : "")
    + " node-card__stage--status-" + dot.status
    + (dot.current ? " node-card__stage--current" : "")
    + (dot.stuck ? " node-card__stage--stuck" : "")
    + (dot.retry ? " node-card__stage--retry" : "");
}

function Proofs({ slots, far }: { slots: ProofSlot[]; far: boolean }) {
  return (
    <span className="node-card__proofs" aria-hidden="true">
      {slots.map((slot) => (
        <span key={slot.key} className={"node-card__proof node-card__proof--" + slot.status + " node-card__proof--" + slot.key} title={slot.title}>
          <span className="node-card__proof-box" />
          {!far && <span className="node-card__proof-label">{slot.label}</span>}
        </span>
      ))}
    </span>
  );
}

export default function CardProcess({ view, detail }: { view: CardProcessView; detail: "full" | "far" }) {
  const far = detail === "far";
  const base = "node-card__process" + (far ? " node-card__process--far" : "");
  const sr = <span className="node-card__process-sr">{processSentence(view)}</span>;
  if (!view.routed) {
    return (
      <div className={base + " node-card__process--unrouted"}>
        {sr}
        <span className="node-card__stage node-card__stage--unrouted" title="Karta zatím nemá proces" aria-hidden="true" />
        {!far && <span className="node-card__process-count" aria-hidden="true">čeká na router</span>}
        <Proofs slots={view.proofs} far={far} />
      </div>
    );
  }
  return (
    <div className={base}>
      {sr}
      {!far && (
        <span className={"node-card__process-profile" + (view.profile === "security" ? " node-card__process-profile--security" : "")}>
          {view.profileLabel}
        </span>
      )}
      <span className="node-card__process-dots" aria-hidden="true">
        {view.dots.map((dot) => <span key={dot.id} className={dotClass(dot)} title={DOT_TITLE(dot)} />)}
      </span>
      {!far && <span className="node-card__process-count" aria-hidden="true">{view.finished}/{view.total}</span>}
      <Proofs slots={view.proofs} far={far} />
    </div>
  );
}
