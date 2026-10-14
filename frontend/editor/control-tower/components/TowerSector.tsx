// Dlaždice sektoru nebo karty s vlastní vrstvou (kontejner): co to je, jak daleko je, co v něm selhalo
// nebo čeká, a zda prošel bránou (u kontejneru stav karty). Rozbalení ukáže vnitřní vrstvu (oblasti,
// sektory, karty, kontejnery); „Vstoupit“ otevře tu vrstvu na plátně. Rozbalení drží rodič.
import { workLabels } from "@/editor/canvas/node-card/components/WorkNow";
import { contentLabel, layerSize, type TowerSector as Sector } from "../logic/tower-model";
import TowerBar from "./TowerBar";
import TowerLayer, { type TowerNav } from "./TowerLayer";

type Props = {
  sector: Sector;
  /** Úroveň dlaždice (1 = nejvyšší); dlaždice hlouběji než `MAX_SECTOR_DEPTH` už `TowerLayer` nekreslí. */
  depth: number;
  nav: TowerNav;
};

export default function TowerSector({ sector, depth, nav }: Props) {
  const open = nav.expanded.has(sector.id);
  const c = sector.counts;
  const waiting = c.waitingHuman + c.proposed;
  const size = layerSize(sector);
  const card = sector.card;
  const cardLabel = card && (card.proposed ? "ke schválení" : !card.statusKnown ? "stav neznámý" : card.status === "idle" ? "v klidu" : workLabels[card.status]);
  return (
    <article className={"tower-sector" + (depth > 1 ? " tower-sector--nested" : "") + (sector.kind === "card" ? " tower-sector--card" : "") + (sector.verified ? " tower-sector--verified" : "")}>
      <header className="tower-sector__head">
        <h4 className="tower-sector__name">{sector.name}</h4>
        {sector.kind === "sector" ? (
          <span className={"tower-sector__gate" + (sector.verified ? " tower-sector__gate--ok" : "")} title={"Brána: " + sector.gateName}>
            {sector.verified ? "✓ ověřeno" : "brána: " + sector.gateName}
          </span>
        ) : (
          <span className="tower-sector__kind" title={"Karta: " + cardLabel}>karta s vrstvou · {cardLabel}</span>
        )}
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
        <button type="button" className="tower-sector__toggle" aria-expanded={open} onClick={() => nav.onToggle(sector.id)}>
          {open ? "Sbalit" : contentLabel(size.cards, size.sectors, size.areas)}
        </button>
        {card && <button type="button" className="tower-sector__open" onClick={() => nav.onOpenNode(sector.id)}>Otevřít kartu</button>}
        <button type="button" className="tower-sector__enter" onClick={() => nav.onEnterLayer(sector.id)}>Vstoupit</button>
      </div>
      {open && (
        <div className="tower-sector__content">
          <TowerLayer layer={sector} depth={depth + 1} nav={nav} />
          {!size.cards && !size.sectors && !size.areas && <p className="tower-sector__empty">Vrstva je prázdná.</p>}
        </div>
      )}
    </article>
  );
}
