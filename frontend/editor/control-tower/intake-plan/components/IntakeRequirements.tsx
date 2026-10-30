// Seznam požadavků pod nadpisem: otevřené požadavky oblasti, odložené s podmínkou otevření, nebo požadavky bez
// oblasti. Prázdný seznam se nekreslí, aby oblast nebyla plná prázdných nadpisů. Pod každým požadavkem je panel
// výslechu srdce (`brief-panel`); jeho odpovědi a spuštění jdou přes `brief` nahoru do `IntakePlan`.
import type { PlanRequirement } from "../logic/intake-plan";
import type { BriefActions } from "../brief-panel/logic/brief-model";
import BriefPanel from "../brief-panel/components/BriefPanel";

type Props = { title: string; items: PlanRequirement[]; deferred?: boolean; brief: BriefActions };

export default function IntakeRequirements({ title, items, deferred = false, brief }: Props) {
  if (!items.length) return null;
  return (
    <section className={"intake-plan__requirements" + (deferred ? " intake-plan__requirements--deferred" : "")} aria-label={title}>
      <span className="intake-plan__eyebrow">{title} · {items.length}</span>
      <ul className="intake-plan__list">
        {items.map(item => (
          <li key={item.id} className="intake-plan__requirement" data-oh-requirement={item.id}>
            <span>{item.title}</span>
            {item.condition && <small className="intake-plan__condition">{item.condition}</small>}
            <BriefPanel requirement={item.id} brief={item.brief} actions={brief} />
          </li>
        ))}
      </ul>
    </section>
  );
}
