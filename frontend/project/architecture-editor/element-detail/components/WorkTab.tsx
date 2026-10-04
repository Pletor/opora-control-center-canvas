import type { NodePhase } from "@/shared/desktop-state/logic/types";
import { pipelineSteps } from "../../component-structure/logic/structure-model";

type Props = {
  nodeId: string;
  phase: NodePhase;
  done: boolean;
  onOpenEditor: (id: string) => void;
};

/** Záložka Práce: kde je práce v pipeline, zda je karta uzavřená a vstup do Editoru nad stejným ID. */
export default function WorkTab({ nodeId, phase, done, onOpenEditor }: Props) {
  return (
    <div className="element-detail__pane">
      <section className="element-detail__links" aria-label="Fáze">
        <h4 className="element-detail__subtitle">Fáze</h4>
        <ol className="element-detail__phases">
          {pipelineSteps(phase).map((step) => (
            <li
              key={step.phase}
              className={`element-detail__phase element-detail__phase--${step.state}`}
              aria-current={step.state === "current" ? "step" : undefined}
            >
              {step.label}
            </li>
          ))}
        </ol>
      </section>
      <section className="element-detail__links" aria-label="Uzavření karty">
        <h4 className="element-detail__subtitle">Uzavření karty</h4>
        <p className={`element-detail__closure${done ? " element-detail__closure--done" : ""}`}>
          {done ? "Karta je uzavřená." : "Karta zatím není uzavřená; uzavírá se v Editoru."}
        </p>
      </section>
      <button type="button" className="element-detail__open" onClick={() => onOpenEditor(nodeId)}>
        Otevřít v Editoru
      </button>
    </div>
  );
}
