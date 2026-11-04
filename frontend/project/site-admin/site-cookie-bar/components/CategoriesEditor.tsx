import { Toggle } from "@/project/site-admin/site-fields/components/Fields";
import { CATEGORIES, DEFAULT_INFO, withCategory, type Category, type CookieBar } from "../logic/cookie-bar";

/** Kategorie cookies, které web používá: zapnutí (nezbytné jsou vždy), vlastní název a popis pro návštěvníka.
 *  Tady se říká jen, jaké kategorie web má; návštěvník je má vždy předem vypnuté. */
export default function CategoriesEditor({ bar, onChange }: { bar: CookieBar; onChange: (bar: CookieBar) => void }) {
  const edit = (category: Category, patch: Partial<{ label: string; description: string }>) =>
    onChange({ ...bar, categoryInfo: { ...bar.categoryInfo, [category]: { label: "", description: "", ...bar.categoryInfo[category], ...patch } } });
  return <fieldset className="site-fields__group">
    <legend className="site-fields__legend">Kategorie</legend>
    <div className="site-cookie-bar__categories">
      {CATEGORIES.map((category) => {
        const on = bar.categories.includes(category);
        const custom = bar.categoryInfo[category];
        return <div key={category} className={"site-cookie-bar__category" + (on ? "" : " site-cookie-bar__category--off")}>
          <Toggle label={DEFAULT_INFO[category].label} checked={on} disabled={category === "necessary"}
            hint={category === "necessary" ? "Vždy zapnuté, bez souhlasu." : "Web je používá; návštěvník je má předem vypnuté."}
            onChange={(next) => onChange(withCategory(bar, category, next))}/>
          {on && <>
            <input className="site-fields__input" value={custom?.label ?? ""} placeholder={DEFAULT_INFO[category].label} aria-label={`${DEFAULT_INFO[category].label}: název pro návštěvníka`} maxLength={80}
              onChange={(event) => edit(category, { label: event.target.value })}/>
            <input className="site-fields__input" value={custom?.description ?? ""} placeholder={DEFAULT_INFO[category].description} aria-label={`${DEFAULT_INFO[category].label}: popis`} maxLength={500}
              onChange={(event) => edit(category, { description: event.target.value })}/>
          </>}
        </div>;
      })}
    </div>
  </fieldset>;
}
