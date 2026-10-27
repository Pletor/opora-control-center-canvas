import type { CanvasNode, CustomerJourney } from "@/shared/types/logic/types";
import { MAX_STEPS, addStep, journeyProblem, previousStepId, stepName, stepRate } from "../logic/journeys";
import JourneyFunnelLink from "./JourneyFunnelLink";
import JourneyStepCard from "./JourneyStepCard";

/** Editor jedné cesty jako trychtýř: název a účel, pod tím svislé karty kroků se šipkou a konverzí mezi nimi,
 * dole „+ Přidat stránku“ a Uložit / Zrušit pro celou cestu (u uložené cesty i Odebrat cestu). Ukládá rodič. */
export default function JourneyFunnelEditor({ journey, pages, isNew, disabled, saving, error, onChange, onSave, onCancel, onRemove }: {
  journey: CustomerJourney; pages: CanvasNode[]; isNew: boolean; disabled: boolean; saving: boolean; error: string;
  onChange: (journey: CustomerJourney) => void; onSave: () => void; onCancel: () => void; onRemove: () => void;
}) {
  const problem = journeyProblem(journey);
  return <li className="domain-map__journey domain-map__journey--editing" data-testid={"architecture-journey-editor-" + journey.id}>
    <div className="domain-map__journey-fields">
      <label>Název cesty<input required maxLength={80} placeholder="Prodej kurzu" disabled={disabled} data-testid="architecture-journey-name"
        value={journey.name} onChange={(event) => onChange({ ...journey, name: event.target.value })}/></label>
      <label>Účel cesty<input maxLength={200} placeholder="Z návštěvníka platící zákazník" disabled={disabled} data-testid="architecture-journey-purpose"
        value={journey.purpose ?? ""} onChange={(event) => onChange({ ...journey, purpose: event.target.value || undefined })}/></label>
    </div>
    <ol className="domain-map__funnel domain-map__funnel--editing">
      {journey.steps.map((step, index) => {
        const previous = previousStepId(journey, index);
        const branch = previous && previous !== journey.steps[index - 1]?.id ? stepName(journey, previous) : undefined;
        return <li key={step.id} className="domain-map__funnel-item">
          {index > 0 && <JourneyFunnelLink rate={stepRate(journey, index)} branchFrom={branch}/>}
          <JourneyStepCard journey={journey} index={index} pages={pages} disabled={disabled} onChange={onChange}/>
        </li>;
      })}
    </ol>
    <button type="button" className="domain-map__funnel-add" disabled={disabled || journey.steps.length >= MAX_STEPS} data-testid="architecture-journey-step-add"
      onClick={() => onChange(addStep(journey, pages.map((page) => page.id)))}>+ Přidat stránku</button>
    {problem && <small role="alert" className="domain-map__journey-problem">{problem}</small>}
    {error && <p role="alert">{error}</p>}
    <div className="ae-row">
      <button type="button" disabled={disabled || problem !== null} data-testid="architecture-journey-save" onClick={onSave}>{saving ? "Ukládám…" : "Uložit cestu"}</button>
      <button type="button" disabled={saving} onClick={onCancel}>Zrušit</button>
      {!isNew && <button type="button" className="domain-map__danger" disabled={disabled} data-testid="architecture-journey-remove" onClick={onRemove}>Odebrat cestu</button>}
    </div>
  </li>;
}
