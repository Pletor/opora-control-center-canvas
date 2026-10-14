// Proces karty jako řada kuliček pod hlavou: barva = kdo pracuje, výplň = jak dopadl, kroužek = kde proces stojí.
// Dílek jen zobrazuje hotový pohled z `logic/card-process.ts`; nic neukládá.
import { DOT_TITLE, processSentence, type CardProcessView, type ProcessDot } from "../logic/card-process";

function dotClass(dot: ProcessDot): string {
  return "node-card__stage"
    + " node-card__stage--kind-" + dot.kind
    + (dot.kind === "critic" && dot.lens ? " node-card__stage--lens-" + dot.lens : "")
    + " node-card__stage--status-" + dot.status
    + (dot.current ? " node-card__stage--current" : "")
    + (dot.stuck ? " node-card__stage--stuck" : "")
    + (dot.retry ? " node-card__stage--retry" : "");
}

export default function CardProcess({ view, detail, kind }: { view: CardProcessView; detail: "full" | "far"; kind: "node" | "sector" }) {
  const far = detail === "far";
  const base = "node-card__process" + (far ? " node-card__process--far" : "");
  const sr = <span className="node-card__process-sr">{processSentence(view)}</span>;
  const proposed = !far && view.proposed > 0 && <span className="node-card__process-proposed">+{view.proposed} ke schválení</span>;
  if (!view.routed) {
    if (kind !== "node") return null;
    return (
      <div className={base + " node-card__process--unrouted"}>
        {sr}
        <span className="node-card__stage node-card__stage--unrouted" title="Karta zatím nemá proces" aria-hidden="true" />
        {!far && <span className="node-card__process-count" aria-hidden="true">čeká na router</span>}
        {proposed}
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
        {view.dots.map((dot) => {
          return <span key={dot.id} className={dotClass(dot)} title={DOT_TITLE(dot)} />;
        })}
      </span>
      {!far && <span className="node-card__process-count" aria-hidden="true">{view.finished}/{view.total}</span>}
      {proposed}
      {!far && view.waitingOnHuman && <span className="node-card__process-human" aria-hidden="true" title="Proces uvízl, čeká na člověka">👤 čeká</span>}
    </div>
  );
}
