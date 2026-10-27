import type { PageSectionRole, PageSite } from "@/shared/types/logic/types";
import { MAX_PAGE_SECTIONS, SECTION_ROLE_LABELS, addSection, moveSection, removeSection, updateSection } from "../logic/page-site";

const ROLES = Object.keys(SECTION_ROLE_LABELS) as PageSectionRole[];

/** Sekce stránky, které si člověk skládá sám: řádek na sekci (role, název, záměr, nahoru, dolů, odebrat) a pod seznamem „Přidat sekci“.
 * Dostane celý `site` a každou změnu vrací jako celý `site` (stejně jako `PageIntentFields`); ukládá rodič. */
export default function PageSectionsEditor({ site, disabled, onChange }: { site: PageSite; disabled: boolean; onChange: (site: PageSite) => void }) {
  const sections = site.sections ?? [];
  return <div className="domain-map__sections-editor" data-testid="architecture-product-sections">
    <span>Sekce stránky</span>
    {sections.length === 0 && <small>Zatím bez sekcí. Přidejte je, ať je jasné, z čeho se stránka skládá.</small>}
    {sections.map((section, index) => <div key={section.id} className="domain-map__section-row" data-testid={"architecture-section-" + section.id}>
      <select aria-label="Role sekce" disabled={disabled} data-testid={"architecture-section-role-" + section.id} value={section.role} onChange={(event) => onChange(updateSection(site, section.id, { role: event.target.value as PageSectionRole }))}>
        {ROLES.map((role) => <option key={role} value={role}>{SECTION_ROLE_LABELS[role]}</option>)}
      </select>
      <input required maxLength={60} aria-label="Název sekce" placeholder="Název sekce" disabled={disabled} data-testid={"architecture-section-name-" + section.id} value={section.name} onChange={(event) => onChange(updateSection(site, section.id, { name: event.target.value }))}/>
      <input maxLength={200} aria-label="Záměr sekce" placeholder="Co má sekce udělat" disabled={disabled} data-testid={"architecture-section-intent-" + section.id} value={section.intent} onChange={(event) => onChange(updateSection(site, section.id, { intent: event.target.value }))}/>
      <span className="domain-map__section-actions">
        <button type="button" aria-label="Posunout nahoru" disabled={disabled || index === 0} data-testid={"architecture-section-up-" + section.id} onClick={() => onChange(moveSection(site, section.id, -1))}>↑</button>
        <button type="button" aria-label="Posunout dolů" disabled={disabled || index === sections.length - 1} data-testid={"architecture-section-down-" + section.id} onClick={() => onChange(moveSection(site, section.id, 1))}>↓</button>
        <button type="button" disabled={disabled} data-testid={"architecture-section-remove-" + section.id} onClick={() => onChange(removeSection(site, section.id))}>Odebrat</button>
      </span>
    </div>)}
    <button type="button" className="domain-map__section-add" disabled={disabled || sections.length >= MAX_PAGE_SECTIONS} data-testid="architecture-section-add" onClick={() => onChange(addSection(site))}>+ Přidat sekci</button>
  </div>;
}
