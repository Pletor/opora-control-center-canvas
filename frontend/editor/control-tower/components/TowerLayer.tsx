// Obsah jedné vrstvy pyramidy v pevném pořadí: pásma oblastí (každé se svými členy) → sektory mimo oblast →
// karty mimo oblast → kontejnerové karty. Stejný dílek kreslí vnitřek oblasti i rozbalené dlaždice;
// `depth` hlídá, kolik úrovní dlaždic se ještě kreslí (součty jsou v datech vždy celé).
import { MAX_SECTOR_DEPTH, type TowerArea as Area, type TowerCard, type TowerLayer as Layer, type TowerSector as Sector } from "../logic/tower-model";
import TowerArea from "./TowerArea";
import TowerCardRow from "./TowerCardRow";
import TowerSector from "./TowerSector";

/** Co dílky pyramidy potřebují od rodiče: rozbalené dlaždice a akce (otevřít kartu, vstoupit do vrstvy). */
export type TowerNav = {
  expanded: ReadonlySet<string>;
  onToggle: (id: string) => void; onOpenNode: (id: string) => void; onEnterLayer: (id: string) => void;
};

type Group = { sectors: Sector[]; cards: TowerCard[]; containers: Sector[] };

/** Členové jedné skupiny (oblasti nebo zbytku vrstvy): mřížka sektorů, řádky karet, mřížka kontejnerů. */
export function TowerGroup({ group, depth, nav }: { group: Group; depth: number; nav: TowerNav }) {
  // Hlouběji než MAX_SECTOR_DEPTH se dlaždice nekreslí (jen karty této vrstvy); součty je zahrnují.
  if (depth > MAX_SECTOR_DEPTH) {
    const hidden = group.sectors.length + group.containers.length;
    return <>
      {group.cards.length > 0 && (
        <ul className="tower-layer__cards">{group.cards.map((c) => <TowerCardRow key={c.id} card={c} onOpenNode={nav.onOpenNode} />)}</ul>
      )}
      {hidden > 0 && <p className="tower-layer__deeper">Dalších {hidden} vrstev se tu nekreslí, součty je zahrnují. Otevři je přes „Vstoupit“.</p>}
    </>;
  }
  return <>
    {group.sectors.length > 0 && (
      <div className="tower-layer__grid">{group.sectors.map((s) => <TowerSector key={s.id} sector={s} depth={depth} nav={nav} />)}</div>
    )}
    {group.cards.length > 0 && (
      <ul className="tower-layer__cards">{group.cards.map((c) => <TowerCardRow key={c.id} card={c} onOpenNode={nav.onOpenNode} />)}</ul>
    )}
    {group.containers.length > 0 && (
      <div className="tower-layer__grid">{group.containers.map((s) => <TowerSector key={s.id} sector={s} depth={depth} nav={nav} />)}</div>
    )}
  </>;
}

export default function TowerLayer({ layer, depth, nav }: { layer: Layer; depth: number; nav: TowerNav }) {
  const areas: Area[] = layer.areas;
  return (
    <div className="tower-layer">
      {areas.map((area) => <TowerArea key={area.id} area={area} depth={depth} nested nav={nav} />)}
      <TowerGroup group={layer} depth={depth} nav={nav} />
    </div>
  );
}
