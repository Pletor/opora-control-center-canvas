// Jedna oblast v pohledu „Požadavky a plán“: jméno, aktivní milník, návrhy srdce s rozhodnutím člověka, otevřené
// a odložené požadavky. Prázdná oblast řekne jednou větou, že tu zatím nic není. Data hotová, události nahoru.
import IntakeMilestone from "./IntakeMilestone";
import IntakeProposal from "./IntakeProposal";
import IntakeRequirements from "./IntakeRequirements";
import type { PlanArea } from "../logic/intake-plan";
import type { MilestoneAction } from "../logic/intake-api";

type Props = { area: PlanArea; busy: string | null; errors: Record<string, string>;
  onDecide: (milestoneId: string, action: MilestoneAction) => void; onOpen: (nodeId: string) => void };

export default function IntakeArea({ area, busy, errors, onDecide, onOpen }: Props) {
  return (
    <article className={"intake-plan__area" + (area.empty ? " intake-plan__area--empty" : "")} data-oh-area={area.id}>
      <header className="intake-plan__area-head">
        <span className="intake-plan__eyebrow">Oblast</span>
        <h3 className="intake-plan__area-title">{area.name}</h3>
      </header>
      {area.empty && <p className="intake-plan__muted">Oblast zatím nemá milník ani požadavky.</p>}
      {!area.empty && !area.milestone && <p className="intake-plan__muted">Aktivní milník zatím není.</p>}
      {area.milestone && <IntakeMilestone milestone={area.milestone} onOpen={onOpen} />}
      {area.proposed.map(item => <IntakeProposal key={item.id} milestone={item} busy={busy !== null} error={errors[item.id] ?? null}
        onDecide={onDecide} onOpen={onOpen} />)}
      <IntakeRequirements title="Otevřené požadavky" items={area.requirements} />
      <IntakeRequirements title="Odložené požadavky" items={area.deferred} deferred />
    </article>
  );
}
