import type { ReactNode } from "react";
import type { PageSite } from "@/shared/types/logic/types";
import { PAGE_INTENT_FIELDS, withPageIntent } from "../logic/page-site";
import PageSectionsEditor from "../../page-sections/components/PageSectionsEditor";
import "../styles/domain-site.css";

/** Pole stránky ve formuláři: cesta a záměr člověka (cíl, působení, popisek v menu); sekce, které člověk skládá v `PageSectionsEditor`.
 * Každá změna vrací celý `site` se zachovanými ostatními klíči. `intent` = slot pro vstup na plátno záměru (tlačítko „Záměr“). */
export default function PageIntentFields({ site, disabled, intent, onChange }: { site: PageSite; disabled: boolean; intent?: ReactNode; onChange: (site: PageSite) => void }) {
  return <>
    {intent && <div className="domain-site__form-intent">{intent}</div>}
    <label>Cesta stránky<input required maxLength={2048} placeholder="/kontakt" disabled={disabled} data-testid="architecture-product-path" value={site.path} onChange={(event) => onChange({ ...site, path: event.target.value })}/><small>Například kontakt uložíme jako /kontakt. Použijte cestu bez domény, parametrů a #.</small></label>
    {PAGE_INTENT_FIELDS.map(({ key, label, max, placeholder }) => <label key={key}>{label}<input maxLength={max} placeholder={placeholder} disabled={disabled} data-testid={"architecture-product-" + key} value={site[key] ?? ""} onChange={(event) => onChange(withPageIntent(site, key, event.target.value))}/></label>)}
    <PageSectionsEditor site={site} disabled={disabled} onChange={onChange}/>
  </>;
}
