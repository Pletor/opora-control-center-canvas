// Velín nad agent-state (návrh „Opora Editor — lean“, rámy 4a/4b): projekt → vrstva → sektor → karta jako pilulky
// seřazené podle `topoIndex`, rozhodnutí pro člověka, další akce a „Teď běží“. Struktura (jména, sektory) jde
// z grafu plátna, stav výhradně z `cards[]` / `decisions[]` / `actions[]`. Čistá funkce, žádné odhady.
import type { Graph } from "@/shared/types/logic/types";
import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";
import { VERB_LABEL } from "@/hub/oporahub-agent-state/logic/actions-model";
import { cardFace, type CardFace } from "@/editor/canvas/card-face/logic/card-face";
import { toneOf, zeroCounts as zero, type Counts, type PillTone } from "@/editor/canvas/card-face/logic/face-tones";

export { TONES, TONE_GLYPH, TONE_LABEL, toneOf, type Counts, type PillTone } from "@/editor/canvas/card-face/logic/face-tones";
export type VelinPill = { nodeId: string; name: string; tone: PillTone; face: CardFace; topo: number };
export type VelinSector = { id: string; name: string; pills: VelinPill[] };
export type VelinLayer = { id: string; label: string; counts: Counts; sectors: VelinSector[] };
export type VelinFilter = "all" | "human" | "problems" | "running";

const LAYER_ORDER = ["backend", "frontend", "database", "library", ""];
const LAYER_NAME: Record<string, string> = { backend: "Backend", frontend: "Frontend", database: "Databáze", library: "Knihovna", "": "Bez vrstvy" };
export const matches = (filter: VelinFilter, tone: PillTone) => filter === "all" || (filter === "human" && tone === "human")
  || (filter === "problems" && (tone === "bad" || tone === "blocked")) || (filter === "running" && tone === "run");

/** Pilulky všech karet, které agent-state zná, s nejbližším sektorem v grafu. */
export function velinPills(graph: Graph, state: AgentState) {
  const byId = new Map(graph.nodes.map(node => [node.id, node]));
  const sectorOf = (id: string) => {
    for (let node = byId.get(byId.get(id)?.parentId ?? ""); node; node = byId.get(node.parentId ?? ""))
      if (node.kind === "sector") return node;
    return undefined;
  };
  const nameOf = (id: string) => byId.get(id)?.name ?? id;
  return (state.cards ?? []).filter(card => byId.get(card.nodeId)?.kind === "node").map(card => {
    const face = cardFace({ nodeId: card.nodeId, card, sector: false, decisions: state.decisions, nameOf });
    const sector = sectorOf(card.nodeId);
    return { pill: { nodeId: card.nodeId, name: nameOf(card.nodeId), tone: toneOf(face), face, topo: card.topoIndex ?? Number.MAX_SAFE_INTEGER },
      layer: card.layer ?? "", sector: sector ? { id: sector.id, name: sector.name } : { id: "", name: "Bez sektoru" } };
  });
}

export function velinModel(graph: Graph, state: AgentState, filter: VelinFilter = "all") {
  const rows = velinPills(graph, state);
  const total = zero();
  rows.forEach(row => { total[row.pill.tone] += 1; });
  const layers = new Map<string, VelinLayer>();
  for (const row of rows) {
    const layer = layers.get(row.layer) ?? { id: row.layer, label: LAYER_NAME[row.layer] ?? row.layer, counts: zero(), sectors: [] };
    layers.set(row.layer, layer);
    layer.counts[row.pill.tone] += 1;
    if (!matches(filter, row.pill.tone)) continue;
    let sector = layer.sectors.find(item => item.id === row.sector.id);
    if (!sector) layer.sectors.push(sector = { ...row.sector, pills: [] });
    sector.pills.push(row.pill);
  }
  for (const layer of layers.values()) layer.sectors.forEach(sector => sector.pills.sort((a, b) => a.topo - b.topo || a.name.localeCompare(b.name)));
  const ordered = [...layers.values()].sort((a, b) => LAYER_ORDER.indexOf(a.id) - LAYER_ORDER.indexOf(b.id) || a.label.localeCompare(b.label));
  const byExecution = new Map((state.cards ?? []).filter(card => card.executionId).map(card => [card.executionId!, card.nodeId]));
  const cardOf = (target: string | null) => !target ? null : rows.some(row => row.pill.nodeId === target) ? target : byExecution.get(target) ?? null;
  const pillOf = (target: string | null) => { const id = cardOf(target); return id ? rows.find(row => row.pill.nodeId === id)?.pill : undefined; };
  // Položka fronty nese odznak PR své karty (shared/pr-badge), aby člověk viděl, že PR agenta je sloučené.
  const decisions = state.decisions.map(item => ({ ...item, nodeId: cardOf(item.targetId), cardName: pillOf(item.targetId)?.name ?? "",
    pr: pillOf(item.targetId)?.face.pr ?? null }));
  const next = state.actions.filter(action => action.status === "ready").slice(0, 5).map(action => ({
    id: action.id, verb: action.verb, label: VERB_LABEL[action.verb] ?? action.verb, nodeId: cardOf(action.targetId),
    cardName: rows.find(row => row.pill.nodeId === cardOf(action.targetId))?.pill.name ?? action.targetId ?? "",
  }));
  const running = rows.filter(row => row.pill.face.lease || row.pill.face.raw.reason === "lease_past_deadline").map(row => row.pill);
  return { total, cards: rows.length, layers: ordered, decisions, next, running };
}
export type VelinView = ReturnType<typeof velinModel>;

/** Díry mapy pro agenty (`mapGaps` s `owner: "agent"`); `more`, když server seznam ořízl. Starší server: null. */
export function mapGapsForAgents(state: AgentState) {
  if (!state.mapGaps) return null;
  return { count: state.mapGaps.filter(item => item.owner === "agent").length, more: (state.mapGapsTotal ?? 0) > state.mapGaps.length };
}
