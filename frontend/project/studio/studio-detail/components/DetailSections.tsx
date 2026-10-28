import type { StudioDetailView } from "../logic/detail-model";

/** Tři oddíly detailu pod sebou: vazby (odkud → kam, druh toku a počet hran), díry mapy (místo a zpráva) a cesty
 * zákazníka s odznakem posledního ověření. Prázdný oddíl řekne, že nic není, aby ticho neznamenalo „nenačteno“.
 * `links = false`: souhrnné vazby úrovně vynechá, protože komponenta ukazuje své přímé vazby z Detailu prvku. */
export default function DetailSections({ view, links = true }: { view: StudioDetailView; links?: boolean }) {
  return <>
    {links && <section className="studio-detail__section" data-testid="studio-detail-links">
      <h3 className="studio-detail__heading">Vazby <span className="studio-detail__count">{view.links.length}</span></h3>
      {view.links.length ? <ul className="studio-detail__list">
        {view.links.map((link) => <li key={link.id} className={"studio-detail__link studio-detail__link--" + link.carries}>
          <span className="studio-detail__swatch" aria-hidden="true"/>
          <span className="studio-detail__link-text">{link.from} → {link.to}</span>
          <span className="studio-detail__link-flow">{link.flow}{link.count > 1 ? ` · ${link.count}` : ""}</span>
        </li>)}
      </ul> : <p className="studio-detail__none">Na této úrovni žádné vazby.</p>}
    </section>}
    <section className="studio-detail__section" data-testid="studio-detail-holes">
      <h3 className="studio-detail__heading">Díry mapy <span className="studio-detail__count">{view.holes.length}</span></h3>
      {view.holes.length ? <ul className="studio-detail__list">
        {view.holes.map((hole, index) => <li key={index} className="studio-detail__hole"><b className="studio-detail__hole-place">{hole.place}</b> {hole.message}</li>)}
      </ul> : <p className="studio-detail__none">Kontrola mapy tu nic nenašla.</p>}
    </section>
    <section className="studio-detail__section" data-testid="studio-detail-journeys">
      <h3 className="studio-detail__heading">Cesty zákazníka <span className="studio-detail__count">{view.journeys.length}</span></h3>
      {view.journeys.length ? <ul className="studio-detail__list">
        {view.journeys.map((journey) => <li key={journey.id} className="studio-detail__journey">
          <span className="studio-detail__journey-name">{journey.name}</span>
          <span className={"studio-detail__badge studio-detail__badge--" + (journey.badge?.tone ?? "none")} title={journey.title}>{journey.badge?.text ?? "Bez odvození"}</span>
        </li>)}
      </ul> : <p className="studio-detail__none">Karta neleží na žádné cestě.</p>}
    </section>
  </>;
}
