import type { CanvasNode, CustomerJourney } from "@/shared/types/logic/types";
import { FROM_NAV, MIN_STEPS, moveStep, previousStepId, removeStep, stepName, updateStep } from "../logic/journeys";

/** Jedna karta kroku trychtýře: vlevo role, stránka (Menu jen u prvního kroku), počet lidí a „Navazuje na“, vpravo
 * co člověk na stránce zažívá a jak na něj stránka působí. Každou změnu hlásí celou novou cestou nahoru (`onChange`). */
export default function JourneyStepCard({ journey, index, pages, disabled, onChange }: {
  journey: CustomerJourney; index: number; pages: CanvasNode[]; disabled: boolean; onChange: (journey: CustomerJourney) => void;
}) {
  const step = journey.steps[index];
  const testId = (part: string) => `architecture-step-${part}-${step.id}`;
  const known = step.page === FROM_NAV || pages.some((page) => page.id === step.page);
  const previous = previousStepId(journey, index);
  const set = (patch: Parameters<typeof updateStep>[2]) => onChange(updateStep(journey, step.id, patch));
  const count = (value: string) => {
    const parsed = Math.floor(Number(value));
    set({ count: value === "" || !Number.isFinite(parsed) ? undefined : Math.max(0, parsed) });
  };
  return <article className="domain-map__step" data-testid={testId("card")}>
    <div className="domain-map__step-main">
      <input className="domain-map__step-role" maxLength={60} aria-label="Role kroku" disabled={disabled} data-testid={testId("label")}
        placeholder={index === 0 ? "Vstupní stránka" : `${index}. Stránka s obsahem zdarma`} value={step.label ?? ""} onChange={(event) => set({ label: event.target.value || undefined })}/>
      <select aria-label="Stránka" disabled={disabled} data-testid={testId("page")} value={step.page} onChange={(event) => set({ page: event.target.value })}>
        {index === 0 && <option value={FROM_NAV}>Menu (vstup z navigace)</option>}
        {pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
        {!known && <option value={step.page}>chybí stránka {step.page}</option>}
      </select>
      <label className="domain-map__step-field">Počet lidí
        <input type="number" min={0} step={1} inputMode="numeric" disabled={disabled} data-testid={testId("count")} value={step.count ?? ""} onChange={(event) => count(event.target.value)}/>
      </label>
      {index > 0 && <label className="domain-map__step-field">Navazuje na
        <select disabled={disabled} data-testid={testId("after")} value={previous ?? ""}
          onChange={(event) => set({ after: event.target.value === journey.steps[index - 1].id ? undefined : event.target.value })}>
          {journey.steps.slice(0, index).map((other) => <option key={other.id} value={other.id}>{stepName(journey, other.id)}</option>)}
        </select>
      </label>}
      <div className="domain-map__step-tools">
        <button type="button" disabled={disabled || index === 0} aria-label="Posunout krok výš" data-testid={testId("up")} onClick={() => onChange(moveStep(journey, step.id, -1))}>↑</button>
        <button type="button" disabled={disabled || index === journey.steps.length - 1} aria-label="Posunout krok níž" data-testid={testId("down")} onClick={() => onChange(moveStep(journey, step.id, 1))}>↓</button>
        <button type="button" disabled={disabled || journey.steps.length <= MIN_STEPS} data-testid={testId("remove")} onClick={() => onChange(removeStep(journey, step.id))}>Odebrat</button>
      </div>
    </div>
    <label className="domain-map__step-experience">Co člověk zažívá a jak stránka působí
      <textarea rows={4} maxLength={400} disabled={disabled} data-testid={testId("experience")}
        placeholder="Např. dostane video zdarma, pozná, že nám může věřit, a chce víc." value={step.experience ?? ""} onChange={(event) => set({ experience: event.target.value || undefined })}/>
    </label>
  </article>;
}
