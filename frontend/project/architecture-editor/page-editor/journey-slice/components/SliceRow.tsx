import type { PageSlice, SliceNeighbour } from "../logic/page-slice";

/** Signál přechodu jako věta; sekce, kterou předchozí stránka nemá, svítí varovně. Chybějící vazba na mapě tichým štítkem. */
function Signal({ item }: { item: SliceNeighbour }) {
  return <span className="journey-slice__signal">
    {item.signal && <span className={"journey-slice__via" + (item.signal.missingSection ? " journey-slice__via--missing" : "")}
      title={item.signal.missingSection ? `Předchozí stránka sekci ${item.signal.missingSection} nemá` : "Co zákazník udělá, aby přešel dál"}>{item.signal.text}</span>}
    {item.branch && <span className="journey-slice__tag">odbočka</span>}
    {item.unrealized && <span className="journey-slice__tag journey-slice__tag--gap" title={"Na mapě zatím nevede vazba: " + item.unrealized}>chybí vazba</span>}
  </span>;
}

/** Sousední krok: role a stránka; stránku, která v mapě je, jde otevřít (přepne rozsah editoru). */
function Neighbour({ item, onOpenPage }: { item: SliceNeighbour; onOpenPage: (pageId: string) => void }) {
  const label = <><span className="journey-slice__role">{item.role}</span> <span className="journey-slice__page">{item.pageLabel}</span></>;
  return item.pageId
    ? <button type="button" className="journey-slice__neighbour" data-testid={"architecture-slice-open-" + item.stepId}
        aria-label={`Otevřít stránku ${item.pageLabel} (${item.role})`} onClick={() => onOpenPage(item.pageId!)}>{label}</button>
    : <span className={"journey-slice__neighbour journey-slice__neighbour--static" + (item.missing ? " journey-slice__neighbour--missing" : "")}>{label}</span>;
}

/** Jeden úsek: odkud (předchozí krok a jak sem zákazník přijde) → tato stránka (role, posun, námitka, pro koho, A/B)
 * → kam (další kroky a jak se k nim jde). Hotová data od rodiče; klik na souseda hlásí `onOpenPage`. */
export default function SliceRow({ slice, onOpenPage }: { slice: PageSlice; onOpenPage: (pageId: string) => void }) {
  return <div className="journey-slice__row" data-testid={"architecture-slice-" + slice.journeyId + "-" + slice.stepId}>
    <div className="journey-slice__from">
      <span className="journey-slice__caption">odkud</span>
      {slice.from ? <><Neighbour item={slice.from} onOpenPage={onOpenPage}/><Signal item={slice.from}/></>
        : <span className="journey-slice__quiet">{slice.entry ?? "začátek cesty"}</span>}
    </div>
    <span className="journey-slice__arrow" aria-hidden="true">→</span>
    <div className="journey-slice__here">
      <span className="journey-slice__caption">tato stránka · krok {slice.step}/{slice.stepCount}</span>
      <strong className="journey-slice__here-role">{slice.role}</strong>
      {slice.shift && <p className="journey-slice__line">Posun: {slice.shift}</p>}
      {slice.objection && <p className="journey-slice__line journey-slice__line--quiet">Námitka: {slice.objection}</p>}
      {(slice.actor || slice.pointA || slice.pointB) && <p className="journey-slice__change">
        {slice.actor && <span>Pro: {slice.actor}</span>}
        {slice.pointA && <span title={slice.pointA}><b className="journey-slice__mark">A ▸</b> {slice.pointA}</span>}
        {slice.pointB && <span title={slice.pointB}><b className="journey-slice__mark">B ▸</b> {slice.pointB}</span>}
      </p>}
    </div>
    <span className="journey-slice__arrow" aria-hidden="true">→</span>
    <div className="journey-slice__to">
      <span className="journey-slice__caption">kam</span>
      {slice.next.length ? <ul className="journey-slice__next-list">
        {slice.next.map((item) => <li key={item.stepId} className="journey-slice__next"><Neighbour item={item} onOpenPage={onOpenPage}/><Signal item={item}/></li>)}
      </ul> : <span className="journey-slice__quiet">konec cesty</span>}
    </div>
  </div>;
}
