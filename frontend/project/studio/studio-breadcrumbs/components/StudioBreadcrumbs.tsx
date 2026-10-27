import "../styles/studio-breadcrumbs.css";

export type StudioCrumb = { id: string | null; label: string; kind: string };

/** Drobečky zanoření: Projekt › doména › stránka › sekce › komponenta. Každý předek je tlačítko, které vystoupí na
 * jeho úroveň (`onOpen`); poslední drobeček je aktuální úroveň. Backspace dělá totéž o jedno patro. */
export default function StudioBreadcrumbs({ crumbs, onOpen }: { crumbs: StudioCrumb[]; onOpen: (id: string | null) => void }) {
  return <nav className="studio-breadcrumbs" aria-label="Zanoření Studia" data-testid="studio-breadcrumbs">
    <ol className="studio-breadcrumbs__list">
      {crumbs.map((crumb, index) => {
        const last = index === crumbs.length - 1;
        return <li key={crumb.id ?? "project"} className="studio-breadcrumbs__item">
          {last
            ? <span className="studio-breadcrumbs__current" aria-current="page"><small className="studio-breadcrumbs__kind">{crumb.kind}</small>{crumb.label}</span>
            : <button type="button" className="studio-breadcrumbs__link" data-testid={"studio-crumb-" + (crumb.id ?? "project")} onClick={() => onOpen(crumb.id)}>
                <small className="studio-breadcrumbs__kind">{crumb.kind}</small>{crumb.label}
              </button>}
        </li>;
      })}
    </ol>
  </nav>;
}
