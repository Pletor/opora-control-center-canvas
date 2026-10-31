// Čistý model výběru na plátně: v jednu chvíli je vybraný nejvýš jeden uzel, blok v kartě, nebo vazba
// (blok patří ke svému uzlu, proto nese oboje). Bez Reactu, testuje se samostatně; App.tsx z výběru
// a aktuálního režimu odvodí, který panel (knihovna vlevo, inspektor vpravo) se má otevřít.
export type Selection = { node: string | null; block: string | null; edge: string | null;
  /** Vybraná karta s otevřeným bočním menu „stopa práce“ (karta bez bloku, docs/navrhy/2026-10-31-panel-bloku.md). */
  trail?: true };

export function emptySelection(): Selection {
  return { node: null, block: null, edge: null };
}

export function selectNode(id: string): Selection {
  return { node: id, block: null, edge: null };
}

/** Blok drží i id svého uzlu, aby karta uzlu zůstala otevřená v knihovně, i když je vybraný jeho dílek. */
export function selectBlock(nodeId: string, blockId: string): Selection {
  return { node: nodeId, block: blockId, edge: null };
}

/** Karta s otevřenou stopou práce: stejné boční menu jako u bloku, jen bez bloku (karty srdce bloky nemají). */
export function selectCardTrail(nodeId: string): Selection {
  return { node: nodeId, block: null, edge: null, trail: true };
}

export function selectEdge(id: string): Selection {
  return { node: null, block: null, edge: id };
}

export function clearSelection(): Selection {
  return emptySelection();
}

/** Režimy plátna, pro které panelsFor umí odvodit panely; „kreslení" má vlastní inspektor mimo tento model. */
export type PanelsMode = "structure" | "text" | "map" | "office" | "storyboard";

export type Panels = {
  drawer: "node" | "block" | "card" | null;
  inspector: "node" | "edge" | "layer" | "scope" | "comment" | "area" | null;
};

/**
 * Který panel se má otevřít pro daný výběr a režim. Struktura: blok vede do knihovny bez inspektoru,
 * karta s otevřenou stopou práce (`selectCardTrail`) do stejné zásuvky v režimu karty, také bez inspektoru,
 * uzel jen do pravého inspektoru, vazba jen do inspektoru, nic vybraného = žádný panel. Komentář i
 * oblast nemají knihovnu (nenesou bloky) a otevřou jen svůj vlastní inspektor. Text: inspektor ukazuje
 * deník vrstvy, pokud vrstva existuje, jinak obecný kontext. Mapa (Velín) a Kancelář panely nepoužívají.
 */
export function panelsFor(sel: Selection, mode: PanelsMode, hasLayer: boolean, selectedKind?: "node" | "sector" | "comment" | "area"): Panels {
  if (mode === "structure") {
    if (sel.block) return { drawer: "block", inspector: null };
    if (sel.node && selectedKind === "comment") return { drawer: null, inspector: "comment" };
    if (sel.node && selectedKind === "area") return { drawer: null, inspector: "area" };
    if (sel.node && sel.trail) return { drawer: "card", inspector: null };
    if (sel.node) return { drawer: null, inspector: "node" };
    if (sel.edge) return { drawer: null, inspector: "edge" };
    return { drawer: null, inspector: null };
  }
  if (mode === "text") {
    return { drawer: null, inspector: hasLayer ? "layer" : "scope" };
  }
  return { drawer: null, inspector: null };
}
