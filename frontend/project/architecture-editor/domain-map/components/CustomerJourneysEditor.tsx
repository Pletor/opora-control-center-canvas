import type { ApplicationSite, CanvasNode } from "@/shared/types/logic/types";
import { FROM_NAV, MAX_JOURNEYS, addJourney, journeyProblem, removeJourney, updateJourney } from "../logic/journeys";

/** Řádek na cestu: název, odkud (Menu nebo stránka), kam (stránka), Odebrat; pod seznamem „+ Přidat cestu“ a Uložit / Zrušit.
 * Konec, jehož stránka z mapy zmizela, zůstane ve výběru jako „chybí stránka …“, aby ho člověk viděl a přepnul. */
export default function CustomerJourneysEditor({ site, pages, disabled, saving, error, onChange, onSave, onCancel }: {
  site: ApplicationSite; pages: CanvasNode[]; disabled: boolean; saving: boolean; error: string;
  onChange: (site: ApplicationSite) => void; onSave: () => void; onCancel: () => void;
}) {
  const journeys = site.journeys ?? [];
  const pageIds = pages.map((page) => page.id);
  const invalid = journeys.some((journey) => !journey.name.trim() || journeyProblem(journey));
  const missing = (id: string) => id !== FROM_NAV && !pageIds.includes(id) && <option value={id}>chybí stránka {id}</option>;
  return <div className="domain-map__sections-editor">
    {journeys.map((journey) => <div key={journey.id} className="domain-map__journey-row" data-testid={"architecture-journey-row-" + journey.id}>
      <input required maxLength={80} aria-label="Název cesty" placeholder="Poptávka z menu" disabled={disabled} data-testid={"architecture-journey-name-" + journey.id} value={journey.name} onChange={(event) => onChange(updateJourney(site, journey.id, { name: event.target.value }))}/>
      <select aria-label="Odkud" disabled={disabled} data-testid={"architecture-journey-from-" + journey.id} value={journey.from} onChange={(event) => onChange(updateJourney(site, journey.id, { from: event.target.value }))}>
        <option value={FROM_NAV}>Menu</option>
        {pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
        {missing(journey.from)}
      </select>
      <span aria-hidden="true" className="domain-map__journey-arrow">→</span>
      <select aria-label="Kam" disabled={disabled} data-testid={"architecture-journey-to-" + journey.id} value={journey.to} onChange={(event) => onChange(updateJourney(site, journey.id, { to: event.target.value }))}>
        {pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
        {missing(journey.to)}
      </select>
      <button type="button" disabled={disabled} data-testid={"architecture-journey-remove-" + journey.id} onClick={() => onChange(removeJourney(site, journey.id))}>Odebrat</button>
      {journeyProblem(journey) && <small role="alert" className="domain-map__journey-problem">{journeyProblem(journey)}</small>}
    </div>)}
    <button type="button" className="domain-map__section-add" disabled={disabled || journeys.length >= MAX_JOURNEYS} data-testid="architecture-journey-add" onClick={() => onChange(addJourney(site, pageIds))}>+ Přidat cestu</button>
    {error && <p role="alert">{error}</p>}
    <div className="ae-row">
      <button type="button" disabled={disabled || invalid} data-testid="architecture-journeys-save" onClick={onSave}>{saving ? "Ukládám…" : "Uložit cesty"}</button>
      <button type="button" disabled={saving} onClick={onCancel}>Zrušit</button>
    </div>
  </div>;
}
