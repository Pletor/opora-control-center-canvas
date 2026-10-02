// Hlava karty: druh (uzel / sektor), fáze, u uzlu s kartou drobný štítek vrstvy (FE / BE / DB /
// Knihovna) a stavu a — u uzavřené karty — zámek. Jen zobrazení; vrstvu a stav počítá `cardView`.
import { CARD_STATUS_LABEL, type CardView } from "@/editor/canvas/node-card/logic/card-model";
import { LAYER_LABEL } from "@/shared/card-context/logic/card-context";

export default function CardHead({
  view,
}: {
  view: Pick<CardView, "kind" | "phase" | "phaseLabel" | "closed" | "doneProposed"> & Partial<Pick<CardView, "cardLayer" | "cardStatus">>;
}) {
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
      {(view.cardLayer || view.cardStatus) && (
        <span className="node-card__badges">
          {view.cardLayer && <span className="node-card__badge" title="Vrstva karty">{LAYER_LABEL[view.cardLayer]}</span>}
          {view.cardStatus && (
            <span className={"node-card__badge node-card__badge--" + view.cardStatus} title="Stav karty">
              {CARD_STATUS_LABEL[view.cardStatus]}
            </span>
          )}
        </span>
      )}
      <span className={"node-card__phase" + (view.phase === "live" ? " node-card__phase--live" : "")} title="Fáze uzlu (plánovací stav člověka)">
        {view.phaseLabel}
      </span>
    </div>
  );
}
