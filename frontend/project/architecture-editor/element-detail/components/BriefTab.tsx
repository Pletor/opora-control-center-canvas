import type { CanvasNode } from "@/shared/types/logic/types";
import type { NodePhase } from "@/shared/desktop-state/logic/types";
import { PHASE_LABEL } from "../../component-structure/logic/structure-model";
import type { SpecState } from "../logic/use-node-spec";
import IdentityForm from "./IdentityForm";

type Props = {
  node: CanvasNode;
  spec: SpecState;
  phase: NodePhase;
  done: boolean;
  disabled: boolean;
  onIdentity: (original: CanvasNode, name: string, purpose: string) => Promise<void>;
};

const MISSING_SPEC = "Zadání se doplňuje v Editoru";

/** Pracovní zadání jen ke čtení: cíl a kritéria dokončení; prázdné nebo nedostupné odkáže do Editoru. */
function SpecView({ spec }: { spec: SpecState }) {
  if (spec.status === "loading") return <p className="element-detail__muted">Načítám zadání…</p>;
  if (spec.status === "error") return <p className="element-detail__muted">{MISSING_SPEC} (zadání je nedostupné: {spec.message})</p>;
  const { goal, acceptance } = spec.spec.fields;
  if (!spec.spec.available || (!goal.trim() && !acceptance.trim())) return <p className="element-detail__muted">{MISSING_SPEC}</p>;
  return (
    <>
      {goal.trim() ? <p className="element-detail__text"><span className="element-detail__lead">Cíl:</span> {goal}</p> : null}
      {acceptance.trim() ? <p className="element-detail__text">{acceptance}</p> : <p className="element-detail__muted">Kritéria zatím nic</p>}
    </>
  );
}

/** Záložka Zadání: identita, kritéria dokončení a stav. Vazby prvku ukazuje jen záložka Vazby. */
export default function BriefTab({ node, spec, phase, done, disabled, onIdentity }: Props) {
  return (
    <div className="element-detail__pane">
      <IdentityForm key={node.id} node={node} disabled={disabled} onIdentity={onIdentity} />
      <section className="element-detail__links" aria-label="Kritéria dokončení">
        <h4 className="element-detail__subtitle">Kritéria dokončení</h4>
        <SpecView spec={spec} />
      </section>
      <section className="element-detail__links" aria-label="Stav">
        <h4 className="element-detail__subtitle">Stav</h4>
        <p className="element-detail__text">
          Fáze: {PHASE_LABEL[phase]} · {done ? "Uzavřeno" : "Neuzavřeno"}
        </p>
      </section>
    </div>
  );
}
