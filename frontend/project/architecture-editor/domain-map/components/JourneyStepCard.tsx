import type { CanvasNode, CustomerJourney } from "@/shared/types/logic/types";
import { FROM_NAV, MIN_STEPS, moveStep, oneLine, previousStepId, previousStepPage, removeStep, stepName, updateStep } from "../logic/journeys";
import { sectionsOfPage } from "../logic/journey-via";
import JourneyStepVia from "./JourneyStepVia";

/** Jedna karta kroku trychtýře: vlevo role, stránka (Menu jen u prvního kroku), „Navazuje na“ a ↑ ↓ Odebrat, vpravo
 * jaký posun na stránce nastane, co ho brzdí (námitka) a „Jak sem přijde“ (signál přechodu z předchozí stránky).
 * Každou změnu hlásí celou novou cestou nahoru (`onChange`). */
export default function JourneyStepCard({ journey, index, pages, disabled, onChange }: {
  journey: CustomerJourney; index: number; pages: CanvasNode[]; disabled: boolean; onChange: (journey: CustomerJourney) => void;
}) {
  const step = journey.steps[index];
  const testId = (part: string) => `architecture-step-${part}-${step.id}`;
  const known = step.page === FROM_NAV || pages.some((page) => page.id === step.page);
  const previous = previousStepId(journey, index);
  const set = (patch: Parameters<typeof updateStep>[2]) => onChange(updateStep(journey, step.id, patch));
  return <article className="domain-map__step" data-testid={testId("card")}>
    <div className="domain-map__step-main">
      <input className="domain-map__step-role" maxLength={60} aria-label="Role kroku" disabled={disabled} data-testid={testId("label")}
        placeholder={index === 0 ? "Vstupní stránka" : `${index}. Stránka s obsahem zdarma`} value={step.label ?? ""} onChange={(event) => set({ label: event.target.value || undefined })}/>
      <select aria-label="Stránka" disabled={disabled} data-testid={testId("page")} value={step.page} onChange={(event) => set({ page: event.target.value })}>
        {index === 0 && <option value={FROM_NAV}>Menu (vstup z navigace)</option>}
        {pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
        {!known && <option value={step.page}>chybí stránka {step.page}</option>}
      </select>
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
    <div className="domain-map__step-why">
      <label className="domain-map__step-text">Posun: co se na stránce změní
        <textarea rows={2} maxLength={160} disabled={disabled} data-testid={testId("shift")} placeholder="Např. z „nevím, že to jde“ na „vím, že to jde a kdo to umí“."
          value={step.shift ?? ""} onChange={(event) => set({ shift: oneLine(event.target.value) || undefined })}/>
      </label>
      <label className="domain-map__step-text">Námitka: co posun brzdí
        <textarea rows={2} maxLength={120} disabled={disabled} data-testid={testId("objection")} placeholder="Např. bojí se, že ho zavalíme telefonáty."
          value={step.objection ?? ""} onChange={(event) => set({ objection: oneLine(event.target.value) || undefined })}/>
      </label>
      <JourneyStepVia index={index} via={step.via} sections={sectionsOfPage(previousStepPage(journey, index), pages)} disabled={disabled}
        testId={testId} onChange={(via) => set({ via })}/>
    </div>
  </article>;
}
