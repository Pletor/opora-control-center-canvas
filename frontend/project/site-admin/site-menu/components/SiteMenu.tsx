import { SITE_MENU, type SiteSection } from "../logic/site-sections";
import "../styles/site-menu.css";

/** Levé menu Správy webu: skupiny Nastavení, Vzhled, GDPR a Design System (`image9.png`). Vybranou sekci drží rodič;
 *  menu jen zobrazuje a hlásí klik. Položka bez editoru nese štítek „brzy“. */
export default function SiteMenu({ value, onSelect }: { value: SiteSection; onSelect: (section: SiteSection) => void }) {
  return <nav className="site-menu" aria-label="Části správy webu">
    {SITE_MENU.map((group) => <div key={group.id} className={"site-menu__group site-menu__group--" + group.id}>
      <h3 className="site-menu__label">{group.label}</h3>
      {group.items.map((entry) => <button key={entry.id} type="button" data-testid={"site-menu-" + entry.id}
        className={"site-menu__item" + (entry.id === value ? " site-menu__item--active" : "") + (entry.ready ? "" : " site-menu__item--later")}
        aria-current={entry.id === value ? "page" : undefined} onClick={() => onSelect(entry.id)}>
        {entry.label}{!entry.ready && <small className="site-menu__soon">brzy</small>}
      </button>)}
    </div>)}
  </nav>;
}
