// Návrh milníku od srdce: název, kritéria s kartami a dvě tlačítka pro člověka. Dílek sám nic neposílá: hlásí
// `onDecide` nahoru a dostane zpět `busy` (běží zápis, tlačítka ztichnou) a `error` (česká věta pod tlačítky).
import { IntakeCriteria } from "./IntakeMilestone";
import type { PlanMilestone } from "../logic/intake-plan";
import type { MilestoneAction } from "../logic/intake-api";

type Props = { milestone: PlanMilestone; busy: boolean; error: string | null;
  onDecide: (milestoneId: string, action: MilestoneAction) => void; onOpen: (nodeId: string) => void };

export default function IntakeProposal({ milestone, busy, error, onDecide, onOpen }: Props) {
  return (
    <section className="intake-plan__proposal" aria-label={`Návrh milníku ${milestone.title}`} data-oh-proposal={milestone.id}>
      <div className="intake-plan__milestone-head">
        <span className="intake-plan__eyebrow">Návrh srdce</span>
        <b className="intake-plan__milestone-title">{milestone.title}</b>
      </div>
      <IntakeCriteria criteria={milestone.criteria} onOpen={onOpen} />
      <div className="intake-plan__actions">
        <button type="button" className="intake-plan__button intake-plan__button--primary" disabled={busy}
          onClick={() => onDecide(milestone.id, "activate")} data-oh-action="activate">Aktivovat</button>
        <button type="button" className="intake-plan__button" disabled={busy}
          onClick={() => onDecide(milestone.id, "reject")} data-oh-action="reject">Zamítnout</button>
        {busy && <small className="intake-plan__muted">Ukládám rozhodnutí…</small>}
      </div>
      {error && <p className="intake-plan__error" role="alert">{error}</p>}
    </section>
  );
}
