// Dlaždice sektoru: co sektor je, jak daleko je, co v něm selhalo nebo čeká, a zda prošel bránou.
// Rozbalení ukáže karty a podsektory; „Vstoupit“ otevře vrstvu sektoru na plátně. Rozbalení drží rodič.
import { MAX_SECTOR_DEPTH, contentLabel, type TowerSector as Sector } from "../logic/tower-model";
import TowerBar from "./TowerBar";
import TowerCardRow from "./TowerCardRow";

type Props = {
  sector: Sector; expanded: ReadonlySet<string>; nested?: boolean;
  /** Úroveň sektoru (1 = v oblasti); hlouběji než `MAX_SECTOR_DEPTH` se podsektory nekreslí, jen počítají. */
  depth?: number;
  onToggle: (id: string) => void; onOpenNode: (id: string) => void; onEnterLayer: (id: string) => void;
};

export default function TowerSector({ sector, expanded, nested, depth = 1, onToggle, onOpenNode, onEnterLayer }: Props) {
  const open = expanded.has(sector.id);
  const c = sector.counts;
  const waiting = c.waitingHuman + c.proposed;
  return (
    <article className={"tower-sector" + (nested ? " tower-sector--nested" : "") + (sector.verified ? " tower-sector--verified" : "")}>
      <header className="tower-sector__head">
        <h4 className="tower-sector__name">{sector.name}</h4>
        <span className={"tower-sector__gate" + (sector.verified ? " tower-sector__gate--ok" : "")} title={"Brána: " + sector.gateName}>
          {sector.verified ? "✓ ověřeno" : "brána: " + sector.gateName}
        </span>
      </header>
      {sector.purpose && <p className="tower-sector__purpose">{sector.purpose}</p>}
      <TowerBar counts={c} />
      <ul className="tower-sector__stats">
        <li className="tower-sector__stat">{c.closed}/{c.cards} karet</li>
        {c.running > 0 && <li className="tower-sector__stat tower-sector__stat--running">{c.running} běží</li>}
        {c.failed > 0 && <li className="tower-sector__stat tower-sector__stat--failed">{c.failed} selhalo</li>}
        {waiting > 0 && <li className="tower-sector__stat tower-sector__stat--waiting">{waiting} čeká</li>}
      </ul>
      <div className="tower-sector__actions">
        <button type="button" className="tower-sector__toggle" aria-expanded={open} onClick={() => onToggle(sector.id)}>
          {open ? "Sbalit" : contentLabel(sector.cards.length, sector.subsectors.length)}
        </button>
        <button type="button" className="tower-sector__enter" onClick={() => onEnterLayer(sector.id)}>Vstoupit</button>
      </div>
      {open && (
        <div className="tower-sector__content">
          {sector.cards.length > 0 && (
            <ul className="tower-sector__cards">{sector.cards.map((card) => <TowerCardRow key={card.id} card={card} onOpenNode={onOpenNode} />)}</ul>
          )}
          {depth < MAX_SECTOR_DEPTH ? sector.subsectors.map((sub) => (
            <TowerSector key={sub.id} sector={sub} expanded={expanded} nested depth={depth + 1} onToggle={onToggle} onOpenNode={onOpenNode} onEnterLayer={onEnterLayer} />
          )) : sector.subsectors.length > 0 && (
            <p className="tower-sector__deeper">Další úrovně ({sector.subsectors.length}) se tu nekreslí, součty je zahrnují. Otevři je přes „Vstoupit“.</p>
          )}
          {!sector.cards.length && !sector.subsectors.length && <p className="tower-sector__empty">Sektor je prázdný.</p>}
        </div>
      )}
    </article>
  );
}
