import type { CanvasNode, CustomerJourney } from "@/shared/types/logic/types";
import { formatCount, previousStepId, stepName, stepPageLabel, stepRate } from "../logic/journeys";
import { derivedStepState, type DerivedJourney } from "../logic/derived-journeys";
import JourneyFunnelLink from "./JourneyFunnelLink";

/** Klidové zobrazení jedné cesty: název a účel, pod tím trychtýř kroků (role · stránka · počet lidí) se šipkami
 * a konverzí mezi nimi. Chybějící stránku ukáže varovně, nerealizovaný přechod tichým štítkem (`derived` od rodiče). */
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
    {derived?.broken && <p className="domain-map__journey-broken" data-testid={"architecture-journey-broken-" + journey.id}>Cesta je přerušená: {derived.broken}</p>}
    <ol className="domain-map__funnel">
      {journey.steps.map((step, index) => {
        const page = stepPageLabel(step.page, pages);
        const state = derivedStepState(derived, step.id);
        const previous = previousStepId(journey, index);
        const branch = previous && index > 0 && previous !== journey.steps[index - 1].id ? stepName(journey, previous) : undefined;
        return <li key={step.id} className="domain-map__funnel-item" data-testid={"architecture-journey-step-" + journey.id + "-" + step.id}>
          {index > 0 && <JourneyFunnelLink rate={stepRate(journey, index)} branchFrom={branch} unrealized={state.unrealized}/>}
          <div className={"domain-map__funnel-step" + (page.missing || state.missing ? " domain-map__funnel-step--missing" : "")}>
            <span className="domain-map__funnel-role">{step.label ?? `${index + 1}. krok`}</span>
            <span className="domain-map__funnel-page">{page.label}</span>
            {step.count !== undefined && <span className="domain-map__funnel-count">{formatCount(step.count)} lidí</span>}
            {step.experience && <p className="domain-map__funnel-experience">{step.experience}</p>}
          </div>
        </li>;
      })}
    </ol>
  </li>;
}
