// Vazby vrstvy pro React Flow: vzhled podle portu, puls nově přidané vazby, obálka předávky a výběr.
// Board je počítá v `useMemo`, takže tažení karty ani překreslení App je nepočítá znovu; druhy uzlů pro
// předávku přicházejí jednou za graf (`BoardIndex.kinds`), ne jako nová mapa pro každou vazbu.
import type { Edge } from "@xyflow/react";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { edgeAppearance } from "./board-model";
import { handoffMark } from "@/editor/canvas/card-checklist/logic/card-checklist";
import { dagLook } from "./dag-edges";

export type LayerEdgesInput = {
  graph: Graph;
  state: DesktopState;
  /** Id uzlů, které plátno právě vykresluje (karty vrstvy a boční bloky). */
  ids: ReadonlySet<string>;
  kinds: ReadonlyMap<string, CanvasNode["kind"]>;
  /** Vazby přidané před chvílí: krátce se animují. */
  added: ReadonlySet<string>;
  selectedEdge: string | null;
  /** Šipky bočních bloků (nejsou v grafu); jdou na konec, beze změny kromě výběru. */
  blockEdges: Edge[];
  /** Zjednodušené vedení: rovná čára místo pravoúhlé (velká vrstva, viz `simpleEdges`). */
  simple?: boolean;
  /** Karty, které už nikoho neblokují (tvář `done`); vazby `next` z nich jsou plné, ostatní přerušované. */
  finished?: ReadonlySet<string>;
};

/** Od kolika vazeb ve vrstvě se kreslí rovně: pravoúhlé vedení na tisících vazeb zdržuje každý snímek. */
export const SIMPLE_EDGES_FROM = 1000;
/** Kreslit vazby vrstvy rovně? Rozhoduje počet vazeb mezi vykreslenými uzly, ne celý graf. */
export const simpleEdges = (graph: Graph, ids: ReadonlySet<string>): boolean => {
  let count = 0;
  for (const e of graph.edges) if (ids.has(e.source) && ids.has(e.target) && ++count > SIMPLE_EDGES_FROM) return true;
  return false;
};

/** Vazba z portu `action`/`rule` vede z téhož úchytu jako blok, vazba z tlačítka bloku z úchytu
 *  `block:<blockId>:<portId>` uvnitř karty; starší vazba bez portu = `next`. Vzhled řeší board-model. */
export function layerEdges({ graph, state, ids, kinds, added, selectedEdge, blockEdges, simple = false, finished }: LayerEdgesInput): Edge[] {
  const cards = new Set([...kinds].filter(([, kind]) => kind === "node" || kind === "sector").map(([id]) => id));
  return graph.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e): Edge => ({ ...e, ...edgeAppearance(e, state.nodes[e.source]?.blocks?.find(b => b.id === e.sourceBlockId)?.ports?.find(p => p.id === e.sourcePortId)), animated: added.has(e.id),
      ...(simple ? { type: "straight", pathOptions: undefined } : {}),
      // Předávka jen barvou: zelená vazba = zpráva je předaná; malá jantarová obálka = hotová karta ji nenechala.
      ...handoffLook(handoffMark(e, state, kinds), edgeAppearance(e).style),
      ...(finished ? dagLook(e, cards, finished) : null), selected: e.id === selectedEdge }))
    .concat(blockEdges.map((e) => ({ ...e, selected: e.id === selectedEdge })));
}

/** Vzhled vazby podle předávky: bez textu. Předáno = zelená čára, chybí = drobná jantarová obálka;
 *  plánovací vazby (zdroj ještě nehotový) zůstávají beze změny, aby plátno nebylo ukřičené. */
export function handoffLook(mark: "sent" | "missing" | null, style: Edge["style"]): Partial<Edge> {
  if (mark === "sent") return { style: { ...style, stroke: "#22c55e", strokeWidth: 2 } };
  if (mark !== "missing") return {};
  return {
    label: "✉",
    labelStyle: { fill: "#f59e0b", fontSize: 12 },
    labelBgStyle: { fill: "#111827", stroke: "#f59e0b" },
    labelBgPadding: [4, 2] as [number, number],
    labelBgBorderRadius: 4,
    labelShowBg: true,
  };
}
