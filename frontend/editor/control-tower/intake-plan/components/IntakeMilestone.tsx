// Aktivní milník oblasti: název, pruh postupu v % a kritéria jako checklist (✓ hotovo, ○ nehotovo). Karty kritéria
// jsou odkazy: klik otevře detail karty stejně jako ostatní položky Velínu. Návrh milníku používá stejný seznam
// kritérií (`IntakeCriteria`), jen bez stavu hotovo.
import { criteriaDone, type PlanCriterion, type PlanMilestone } from "../logic/intake-plan";

export function IntakeCriteria({ criteria, onOpen }: { criteria: PlanCriterion[]; onOpen: (nodeId: string) => void }) {
  return (
    <ul className="intake-plan__criteria">
      {criteria.map(criterion => (
        <li key={criterion.id} className={"intake-plan__criterion" + (criterion.done ? " intake-plan__criterion--done" : "")}
          data-oh-criterion={criterion.id} data-oh-done={criterion.done === null ? "" : String(criterion.done)}>
          {criterion.done !== null && <span className="intake-plan__check" aria-label={criterion.done ? "hotovo" : "nehotovo"}>
            {criterion.done ? "✓" : "○"}</span>}
          <span className="intake-plan__criterion-text">{criterion.text}</span>
          <span className="intake-plan__cards">
            {criterion.cards.map(card => (
              <button key={card.id} type="button" className={"intake-plan__card" + (card.done ? " intake-plan__card--done" : "")}
                onClick={() => onOpen(card.id)} title={card.done === null ? card.name : `${card.name} · ${card.done ? "hotovo" : "nehotovo"}`}
                data-oh-node-id={card.id}>{card.name}</button>
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function IntakeMilestone({ milestone, onOpen }: { milestone: PlanMilestone; onOpen: (nodeId: string) => void }) {
  const progress = milestone.progress ?? 0;
  return (
    <section className="intake-plan__milestone" aria-label={`Aktivní milník ${milestone.title}`} data-oh-milestone={milestone.id}>
      <div className="intake-plan__milestone-head">
        <span className="intake-plan__eyebrow">Aktivní milník</span>
        <b className="intake-plan__milestone-title">{milestone.title}</b>
        <small className="intake-plan__muted">{criteriaDone(milestone)}{milestone.done ? " · splněno" : ""}</small>
      </div>
      <div className="intake-plan__progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}
        aria-label="Postup milníku">
        <i className={"intake-plan__progress-fill" + (milestone.done ? " intake-plan__progress-fill--done" : "")} style={{ width: `${progress}%` }} />
      </div>
      <small className="intake-plan__progress-text">{milestone.progress === null ? "postup neznámý" : `${progress} %`}</small>
      <IntakeCriteria criteria={milestone.criteria} onOpen={onOpen} />
    </section>
  );
}
