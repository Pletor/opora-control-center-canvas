// Obsah jedné vrstvy pyramidy v pevném pořadí: pásma oblastí (každé se svými členy) → sektory mimo oblast →
// karty mimo oblast → kontejnerové karty. Stejný dílek kreslí kořen, vnitřek oblasti i rozbalené dlaždice;
// `depth` hlídá, kolik úrovní dlaždic se ještě kreslí (součty jsou v datech vždy celé), `siblings` je počet
// členů celé vrstvy pro výchozí rozbalení první úrovně větvení.
import { MAX_SECTOR_DEPTH, type TowerCard, type TowerLayer as Layer, type TowerSector as Sector } from "../logic/tower-model";
import { layerChildren } from "../logic/tower-view";
import TowerArea from "./TowerArea";
import TowerCardRow from "./TowerCardRow";
import TowerSector from "./TowerSector";

/** Co dílky pyramidy potřebují od rodiče: rozbalení (s výchozím stavem) a akce (otevřít kartu, vstoupit do vrstvy). */
export type TowerNav = {
  /** Projekt a workspace pro zadání, která se z dlaždic kopírují agentovi (router). */
  project: string; workspace: string;
  isOpen: (id: string, byDefault: boolean) => boolean;
  onToggle: (id: string, open: boolean) => void;
  onOpenNode: (id: string) => void; onEnterLayer: (id: string) => void;
};

type Group = { sectors: Sector[]; cards: TowerCard[]; containers: Sector[] };
type GroupProps = { group: Group; depth: number; siblings: number; nav: TowerNav };

/** Členové jedné skupiny (oblasti nebo zbytku vrstvy): mřížka sektorů, řádky karet, mřížka kontejnerů. */
export function TowerGroup({ group, depth, siblings, nav }: GroupProps) {
  const cards = group.cards.length > 0 && (
    <ul className="tower-layer__cards">{group.cards.map((c) => <TowerCardRow key={c.id} card={c} onOpenNode={nav.onOpenNode} />)}</ul>
  );
  // Hlouběji než MAX_SECTOR_DEPTH se dlaždice nekreslí (jen karty této vrstvy); součty je zahrnují.
  if (depth > MAX_SECTOR_DEPTH) {
    const hidden = group.sectors.length + group.containers.length;
    return <>
      {cards}
      {hidden > 0 && <p className="tower-layer__deeper">Dalších {hidden} vrstev se tu nekreslí, součty je zahrnují. Otevři je přes „Vstoupit“.</p>}
    </>;
  }
  const grid = (list: Sector[]) => list.length > 0 && (
    <div className="tower-layer__grid">{list.map((s) => <TowerSector key={s.id} sector={s} depth={depth} siblings={siblings} nav={nav} />)}</div>
  );
  return <>{grid(group.sectors)}{cards}{grid(group.containers)}</>;
}

export default function TowerLayer({ layer, depth, nav, top }: { layer: Layer; depth: number; nav: TowerNav; top?: boolean }) {
  const siblings = layerChildren(layer);
  return (
    <div className="tower-layer">
      {layer.areas.map((area) => <TowerArea key={area.id} area={area} depth={depth} siblings={siblings} nested={!top} nav={nav} />)}
      <TowerGroup group={layer} depth={depth} siblings={siblings} nav={nav} />
    </div>
  );
}
