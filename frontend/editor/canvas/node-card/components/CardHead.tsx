// Hlava karty: druh (uzel / sektor), fáze, u uzlu s kartou drobný štítek vrstvy (FE / BE / DB /
// Knihovna) a stavu, tichý počet otevřených podnětů k dalšímu vývoji, ⚠ „zadání se změnilo“ (schránka zadání) a — u uzavřené karty — zámek. Jen zobrazení; vrstvu a stav počítá `cardView`.
import { CARD_STATUS_LABEL, type CardView } from "@/editor/canvas/node-card/logic/card-model";
import { LAYER_LABEL } from "@/shared/card-context/logic/card-context";

export default function CardHead({
  view,
}: {
  view: Pick<CardView, "kind" | "phase" | "phaseLabel" | "closed" | "doneProposed"> & Partial<Pick<CardView, "cardLayer" | "cardStatus" | "cardModel" | "cardEffort" | "waitingOnHuman" | "openIdeas" | "briefChanged">>;
}) {
  return (
    <div className="node-card__head">
      <span className="node-card__kind">{view.kind === "sector" ? "SEKTOR" : "UZEL"}</span>
      {!view.closed && !!view.waitingOnHuman?.length && (
        <span className="node-card__badge node-card__badge--waiting" role="status"
          title={view.waitingOnHuman.map((item) => item.ask).join("\n")}>
          👤 Čeká na tebe: {view.waitingOnHuman[0].ask}
        </span>
      )}
      {view.closed && (
        <span className="node-card__lock" title="Karta je uzavřená: bloky a porty jsou jen ke čtení." aria-label="Uzavřená karta">
          <span style={{ color: "#16a34a" }}>✓</span> 🔒
        </span>
      )}
      {view.doneProposed && (
        <span className="node-card__lock node-card__lock--proposed" title="Agent navrhl uzavření; potvrzuje člověk." aria-label="Uzavření navržené agentem">
          ⌛
        </span>
      )}
      {!!view.briefChanged && (
        <span className="node-card__badge node-card__badge--brief-changed" role="status"
          title={`Zadání se změnilo: ${view.briefChanged} ${view.briefChanged === 1 ? "fragment schránky má" : "fragmenty schránky mají"} novější revizi, než ze které karta vznikla (detail karty, záložka Zadání).`}>
          ⚠ zadání se změnilo
        </span>
      )}
      {!!view.openIdeas && (
        <span className="node-card__badge" title={`Podněty k dalšímu vývoji: ${view.openIdeas} otevřených (detail karty, záložka Podněty)`}>
          💡 {view.openIdeas}
        </span>
      )}
      {(view.cardLayer || view.cardStatus || view.cardModel) && (
        <span className="node-card__badges">
          {view.cardLayer && <span className="node-card__badge" title="Vrstva karty">{LAYER_LABEL[view.cardLayer]}</span>}
          {view.cardModel && <span className="node-card__badge" title={"Model: " + view.cardModel + (view.cardEffort ? ", effort: " + view.cardEffort : "")}>{view.cardModel}</span>}
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
