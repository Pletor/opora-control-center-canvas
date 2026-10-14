// Pásmo oblasti: barevný pruh stejné barvy jako rámeček oblasti na plátně, název, účel a vlastní součty;
// uvnitř mřížka sektorů a pod ní karty, které leží v oblasti mimo sektor.
import type { TowerArea as Area } from "../logic/tower-model";
import TowerBar from "./TowerBar";
import TowerCardRow from "./TowerCardRow";
import TowerSector from "./TowerSector";

type Props = {
  area: Area; expanded: ReadonlySet<string>;
  onToggle: (id: string) => void; onOpenNode: (id: string) => void; onEnterLayer: (id: string) => void;
};

export default function TowerArea({ area, expanded, onToggle, onOpenNode, onEnterLayer }: Props) {
  const c = area.counts;
  const extra = (c.running ? " · " + c.running + " pracuje" : "") + (c.failed ? " · " + c.failed + " selhalo" : "");
  return (
    <section className="tower-area" data-color={area.color} aria-label={"Oblast " + area.name}>
      <header className="tower-area__head">
        <h3 className="tower-area__name">{area.name}</h3>
        <span className="tower-area__counts">{c.closed}/{c.cards} hotovo{extra}</span>
      </header>
      {area.purpose && <p className="tower-area__purpose">{area.purpose}</p>}
      <TowerBar counts={c} />
      {area.sectors.length > 0 && (
        <div className="tower-area__grid">
          {area.sectors.map((sector) => (
            <TowerSector key={sector.id} sector={sector} expanded={expanded} onToggle={onToggle} onOpenNode={onOpenNode} onEnterLayer={onEnterLayer} />
          ))}
        </div>
      )}
      {area.cards.length > 0 && (
        <ul className="tower-area__cards">{area.cards.map((card) => <TowerCardRow key={card.id} card={card} onOpenNode={onOpenNode} />)}</ul>
      )}
      {!area.sectors.length && !area.cards.length && <p className="tower-area__empty">V oblasti zatím nic neleží.</p>}
    </section>
  );
}
