import type { PageSite } from "@/shared/types/logic/types";
import { PAGE_INTENT_FIELDS, withPageIntent } from "../logic/page-site";
import PageSections from "./PageSections";

/** Pole stránky ve formuláři: cesta a záměr člověka (cíl, působení, popisek v menu); sekce jen jako přehled od agenta.
 * Každá změna vrací celý `site` se zachovanými ostatními klíči. */
export default function PageIntentFields({ site, disabled, onChange }: { site: PageSite; disabled: boolean; onChange: (site: PageSite) => void }) {
  return <>
    <label>Cesta stránky<input required maxLength={2048} placeholder="/kontakt" disabled={disabled} data-testid="architecture-product-path" value={site.path} onChange={(event) => onChange({ ...site, path: event.target.value })}/><small>Například kontakt uložíme jako /kontakt. Použijte cestu bez domény, parametrů a #.</small></label>
    {PAGE_INTENT_FIELDS.map(({ key, label, max, placeholder }) => <label key={key}>{label}<input maxLength={max} placeholder={placeholder} disabled={disabled} data-testid={"architecture-product-" + key} value={site[key] ?? ""} onChange={(event) => onChange(withPageIntent(site, key, event.target.value))}/></label>)}
    <div className="domain-map__form-sections"><span>Sekce stránky</span>
      <PageSections sections={site.sections} detailed/>
      <small>{site.sections?.length ? "Sekce navrhuje agent; tady je jen vidíte." : "Zatím bez sekcí. Navrhne je agent podle cíle stránky."}</small>
    </div>
  </>;
}
