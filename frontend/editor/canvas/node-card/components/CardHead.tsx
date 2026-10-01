// Hlava karty: druh (uzel / sektor), fáze a — u uzavřené karty — zámek. Jen zobrazení, žádná logika.
import type { CardView } from "@/editor/canvas/node-card/logic/card-model";

export default function CardHead({ view }: { view: Pick<CardView, "kind" | "phase" | "phaseLabel" | "closed" | "doneProposed"> }) {
  return (
    <div className="node-card__head">
      <span className="node-card__kind">{view.kind === "sector" ? "SEKTOR" : "UZEL"}</span>
      {view.closed && (
        <span className="node-card__lock" title="Karta je uzavřená: bloky a porty jsou jen ke čtení." aria-label="Uzavřená karta">
          🔒
        </span>
      )}
      {view.doneProposed && (
        <span className="node-card__lock node-card__lock--proposed" title="Agent navrhl uzavření; potvrzuje člověk." aria-label="Uzavření navržené agentem">
          ⌛
        </span>
      )}
      <span className={"node-card__phase" + (view.phase === "live" ? " node-card__phase--live" : "")} title="Fáze uzlu (plánovací stav člověka)">
        {view.phaseLabel}
      </span>
    </div>
  );
}
