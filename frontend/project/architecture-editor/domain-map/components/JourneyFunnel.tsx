import type { CanvasNode, CustomerJourney } from "@/shared/types/logic/types";
import { previousStepId, stepName, stepPageLabel, stepSignal } from "../logic/journeys";
import { derivedStepState, type DerivedJourney } from "../logic/derived-journeys";
import JourneyFunnelLink from "./JourneyFunnelLink";

/** Klidové zobrazení jedné cesty jako proměny zákazníka: název a účel, pro koho a bod A nahoře, pod tím trychtýř kroků
 * (role · stránka, posun, menším písmem námitka) se signálem přechodu na šipkách a dole bod B. Bez čísel. Chybějící
 * stránku ukáže varovně, nerealizovaný přechod tichým štítkem (`derived` od rodiče). */
export default function JourneyFunnel({ journey, pages, derived, disabled, onEdit }: {
  journey: CustomerJourney; pages: CanvasNode[]; derived: DerivedJourney | undefined; disabled: boolean; onEdit: () => void;
}) {
  return <li className="domain-map__journey" data-testid={"architecture-journey-" + journey.id}>
    <header className="domain-map__journey-head">
      <div>
        <strong className="domain-map__journey-name">{journey.name}</strong>
        {journey.purpose && <p className="domain-map__journey-purpose">{journey.purpose}</p>}
      </div>
      <button type="button" className="domain-map__section-add" disabled={disabled} data-testid={"architecture-journey-edit-" + journey.id} onClick={onEdit}>Upravit</button>
    </header>
    {journey.actor && <p className="domain-map__journey-actor" data-testid={"architecture-journey-actor-" + journey.id}>Pro: {journey.actor}</p>}
    {journey.pointA && <p className="domain-map__journey-point" data-testid={"architecture-journey-a-" + journey.id}><b className="domain-map__journey-point-mark">A ▸</b> {journey.pointA}</p>}
    {derived?.broken && <p className="domain-map__journey-broken" data-testid={"architecture-journey-broken-" + journey.id}>Cesta je přerušená: {derived.broken}</p>}
    <ol className="domain-map__funnel">
      {journey.steps.map((step, index) => {
        const page = stepPageLabel(step.page, pages);
        const state = derivedStepState(derived, step.id);
        const previous = previousStepId(journey, index);
        const branch = previous && index > 0 && previous !== journey.steps[index - 1].id ? stepName(journey, previous) : undefined;
        const signal = stepSignal(journey, index, pages);
        return <li key={step.id} className="domain-map__funnel-item" data-testid={"architecture-journey-step-" + journey.id + "-" + step.id}>
          {index > 0 && <JourneyFunnelLink signal={signal?.text} missingSection={signal?.missingSection} branchFrom={branch} unrealized={state.unrealized}/>}
          <div className={"domain-map__funnel-step" + (page.missing || state.missing ? " domain-map__funnel-step--missing" : "")}>
            <span className="domain-map__funnel-role">{step.label ?? `${index + 1}. krok`}</span>
            <span className="domain-map__funnel-page">{page.label}</span>
            {step.shift && <p className="domain-map__funnel-shift">Posun: {step.shift}</p>}
            {step.objection && <p className="domain-map__funnel-objection">Námitka: {step.objection}</p>}
          </div>
        </li>;
      })}
    </ol>
    {journey.pointB && <p className="domain-map__journey-point domain-map__journey-point--b" data-testid={"architecture-journey-b-" + journey.id}><b className="domain-map__journey-point-mark">B ▸</b> {journey.pointB}</p>}
  </li>;
}
