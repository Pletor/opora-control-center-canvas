// Seznam požadavků pod nadpisem: otevřené požadavky oblasti, odložené s podmínkou otevření, nebo požadavky bez
// oblasti. Prázdný seznam se nekreslí, aby oblast nebyla plná prázdných nadpisů.
import type { PlanRequirement } from "../logic/intake-plan";

export default function IntakeRequirements({ title, items, deferred = false }: { title: string; items: PlanRequirement[]; deferred?: boolean }) {
  if (!items.length) return null;
  return (
    <section className={"intake-plan__requirements" + (deferred ? " intake-plan__requirements--deferred" : "")} aria-label={title}>
      <span className="intake-plan__eyebrow">{title} · {items.length}</span>
      <ul className="intake-plan__list">
        {items.map(item => (
          <li key={item.id} className="intake-plan__requirement" data-oh-requirement={item.id}>
            <span>{item.title}</span>
            {item.condition && <small className="intake-plan__condition">{item.condition}</small>}
          </li>
        ))}
      </ul>
    </section>
  );
}
