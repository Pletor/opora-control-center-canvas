import type { NodePhase } from "@/shared/desktop-state/logic/types";
import { PHASE_LABEL } from "../logic/element-tone";
import type { SpecState } from "../logic/use-node-spec";

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

/** Kritéria dokončení a stav prvku jen ke čtení; sdílí záložka Zadání v Detailu prvku i panel detailu Studia. */
export default function BriefStatus({ spec, phase, done }: { spec: SpecState; phase: NodePhase; done: boolean }) {
  return (
    <>
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
    </>
  );
}
