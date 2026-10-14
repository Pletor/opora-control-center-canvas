// Jak se pyramida Velínu ukáže, bez Reactu: průchozí řetěz (vrstvy s jediným kontejnerem se přeskočí a
// zůstane po nich drobek), výchozí rozbalení první úrovně větvení a paměť rozbalení per projekt.
import type { Tower, TowerLayer, TowerSector } from "./tower-model";

export type ChainLink = { id: string; name: string };
export type CollapsedLayer = { chain: ChainLink[]; layer: TowerLayer };

/** Celá kořenová vrstva Velínu (oblasti na kořeni a vše mimo ně) jako jedna vrstva. */
export function rootLayer(tower: Tower): TowerLayer {
  return { areas: tower.areas, sectors: tower.loose, cards: tower.looseCards, containers: tower.looseContainers };
}

/** Jediná dlaždice vrstvy, když vrstva nic jiného nemá (žádné oblasti ani karty); jinak `null`. */
function onlyBlock(layer: TowerLayer): TowerSector | null {
  if (layer.areas.length || layer.cards.length) return null;
  const blocks = [...layer.sectors, ...layer.containers];
  return blocks.length === 1 ? blocks[0] : null;
}

/**
 * Průchozí řetěz: dokud vrstva obsahuje jen jednu dlaždici (sektor nebo kartu s vrstvou) a nic dalšího,
 * sestoupí do ní. Vrátí přeskočené články (pro drobek) a vrstvu, kde se pyramida skutečně větví.
 * Ochrana proti cyklu: každý článek nejvýš jednou.
 */
export function collapseChain(layer: TowerLayer): CollapsedLayer {
  const chain: ChainLink[] = [];
  const seen = new Set<string>();
  let current = layer;
  for (let block = onlyBlock(current); block && !seen.has(block.id); block = onlyBlock(current)) {
    seen.add(block.id);
    chain.push({ id: block.id, name: block.name });
    current = block;
  }
  return { chain, layer: current };
}

/** Kolik přímých členů vrstva má (dlaždice i karty, i uvnitř oblastí). */
export function layerChildren(layer: TowerLayer): number {
  return [layer, ...layer.areas].reduce((n, g) => n + g.sectors.length + g.cards.length + g.containers.length, 0);
}

/** Výchozí rozbalení: dlaždice první úrovně vrstvy, která se větví (2+ členů), je rozbalená; hlubší sbalené. */
export function defaultOpen(depth: number, siblings: number): boolean {
  return depth === 1 && siblings >= 2;
}

/** Ruční přepnutí rozbalení přebíjí výchozí stav: id → rozbaleno. */
export type OpenOverrides = Record<string, boolean>;
type Storage = Pick<globalThis.Storage, "getItem" | "setItem">;

export const openKey = (project: string) => "opora:velin:" + project;

/** Přečte paměť rozbalení projektu; poškozený zápis nebo nedostupné úložiště = prázdná paměť. */
export function readOpen(storage: Storage | undefined, project: string): OpenOverrides {
  try {
    const raw = storage?.getItem(openKey(project));
    const value: unknown = raw ? JSON.parse(raw) : {};
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return Object.fromEntries(Object.entries(value).filter(([, v]) => typeof v === "boolean")) as OpenOverrides;
  } catch {
    return {};
  }
}

/** Zapíše paměť rozbalení; chyba úložiště (soukromé okno, plné) se tiše ignoruje. */
export function writeOpen(storage: Storage | undefined, project: string, value: OpenOverrides): void {
  try {
    storage?.setItem(openKey(project), JSON.stringify(value));
  } catch {
    /* paměť rozbalení je jen pohodlí */
  }
}
