import type { NavItem, PageNav as PageNavData } from "../logic/page-nav";
import "../styles/page-nav.css";

function row(items: NavItem[], level: "top" | "sub", onOpen: (id: string) => void) {
  return <ul className={`page-nav__list page-nav__list--${level}`}>
    {items.map((item) => <li key={item.id}>
      <button type="button" data-testid={"architecture-page-nav-" + item.id}
        className={"page-nav__item" + (item.current ? " page-nav__item--current" : item.onPath ? " page-nav__item--path" : "")}
        style={level === "sub" && item.depth > 1 ? { marginLeft: (item.depth - 1) * 10 } : undefined}
        aria-current={item.current ? "page" : undefined} onClick={() => onOpen(item.id)}>
        {level === "sub" ? "↳ " : ""}{item.label}
      </button>
    </li>)}
  </ul>;
}

/** Pruh navigace domény nad plátnem: hlavní stránky jako NAVBAR na Mapě domény, pod nimi podstránky aktivní větve.
 * Otevřená stránka je zvýrazněná (`aria-current`), její předek tišeji; klik hlásí `onOpen(pageId)` rodiči. */
export default function PageNav({ nav, onOpen }: { nav: PageNavData; onOpen: (pageId: string) => void }) {
  if (!nav.top.length) return null;
  return <nav className="page-nav" aria-label="Navigace domény" data-testid="architecture-page-nav">
    <strong className="page-nav__label" aria-hidden="true">NAVBAR</strong>
    {row(nav.top, "top", onOpen)}
    {nav.sub.length > 0 && row(nav.sub, "sub", onOpen)}
  </nav>;
}
