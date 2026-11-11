import type { PageSectionRole, PageSite } from "@/shared/types/logic/types";
import { MAX_PAGE_SECTIONS, SECTION_MOVES_MAX, SECTION_ROLE_LABELS, addSection, moveSection, removeSection, updateSection } from "../../domain-site/logic/page-site";
import "../styles/page-sections.css";

const ROLES = Object.keys(SECTION_ROLE_LABELS) as PageSectionRole[];

/** Sekce stránky, které si člověk skládá sám: blok na sekci (role, název, záměr, nahoru, dolů, odebrat a pod tím „Čím posouvá“)
 * a pod seznamem „Přidat sekci“. Sdílí ho formulář stránky ve Struktuře plátna 2 i záložka Stránka v Detailu prvku.
 * Dostane celý `site` a každou změnu vrací jako celý `site` (stejně jako `PageIntentFields`); ukládá rodič. */
export default function PageSectionsEditor({ site, disabled, onChange }: { site: PageSite; disabled: boolean; onChange: (site: PageSite) => void }) {
  const sections = site.sections ?? [];
  return <div className="page-sections" data-testid="architecture-product-sections">
    <span className="page-sections__title">Sekce stránky</span>
    {sections.length === 0 && <small className="page-sections__empty">Zatím bez sekcí. Přidejte je, ať je jasné, z čeho se stránka skládá.</small>}
    {sections.map((section, index) => <div key={section.id} className="page-sections__row" data-testid={"architecture-section-" + section.id}>
      <select className="page-sections__role" aria-label="Role sekce" disabled={disabled} data-testid={"architecture-section-role-" + section.id} value={section.role} onChange={(event) => onChange(updateSection(site, section.id, { role: event.target.value as PageSectionRole }))}>
        {ROLES.map((role) => <option key={role} value={role}>{SECTION_ROLE_LABELS[role]}</option>)}
      </select>
      <input className="page-sections__name" required maxLength={60} aria-label="Název sekce" placeholder="Název sekce" disabled={disabled} data-testid={"architecture-section-name-" + section.id} value={section.name} onChange={(event) => onChange(updateSection(site, section.id, { name: event.target.value }))}/>
      <input className="page-sections__intent" maxLength={200} aria-label="Záměr sekce" placeholder="Co má sekce udělat" disabled={disabled} data-testid={"architecture-section-intent-" + section.id} value={section.intent} onChange={(event) => onChange(updateSection(site, section.id, { intent: event.target.value }))}/>
      <span className="page-sections__actions">
        <button type="button" className="page-sections__button" aria-label="Posunout nahoru" disabled={disabled || index === 0} data-testid={"architecture-section-up-" + section.id} onClick={() => onChange(moveSection(site, section.id, -1))}>↑</button>
        <button type="button" className="page-sections__button" aria-label="Posunout dolů" disabled={disabled || index === sections.length - 1} data-testid={"architecture-section-down-" + section.id} onClick={() => onChange(moveSection(site, section.id, 1))}>↓</button>
        <button type="button" className="page-sections__button" disabled={disabled} data-testid={"architecture-section-remove-" + section.id} onClick={() => onChange(removeSection(site, section.id))}>Odebrat</button>
      </span>
      <label className="page-sections__moves">
        <span className="page-sections__moves-label">Čím posouvá</span>
        <input maxLength={SECTION_MOVES_MAX} placeholder="Rozptýlí obavu ze spamu: jen e-mail, ozveme se jednou." disabled={disabled} data-testid={"architecture-section-moves-" + section.id} value={section.moves ?? ""} onChange={(event) => onChange(updateSection(site, section.id, { moves: event.target.value }))}/>
      </label>
    </div>)}
    <button type="button" className="page-sections__button page-sections__button--add" disabled={disabled || sections.length >= MAX_PAGE_SECTIONS} data-testid="architecture-section-add" onClick={() => onChange(addSection(site))}>+ Přidat sekci</button>
  </div>;
}
