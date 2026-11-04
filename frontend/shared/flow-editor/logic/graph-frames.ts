// Úpravy poznámek a rámců grafu jako čisté funkce (stejně jako `graph-edit.ts`): každá vrací nový graf. Pravidla rámců
// (souvislý řetězec, bez spouštěče, AI uzel se sub-uzly) hlídá kontrola grafu na serveru; tady se jen skládá tvar.
import type { FlowGraph, FlowGroup, FlowNote, Point } from "./flow-types";

const nextId = (prefix: string, taken: readonly { id: string }[]) => {
  let n = taken.length + 1;
  while (taken.some((item) => item.id === `${prefix}-${n}`)) n += 1;
  return `${prefix}-${n}`;
};

export function addNote(graph: FlowGraph, at: Point, content = "## Poznámka\nCo se tady děje a proč."): FlowGraph {
  const notes = graph.notes ?? [];
  const note: FlowNote = { id: nextId("poznamka", notes), content, x: Math.round(at.x), y: Math.round(at.y), width: 260, height: 160, color: 1 };
  return { ...graph, notes: [...notes, note] };
}

/** Obsah, barva, poloha nebo velikost poznámky; čísla se zaokrouhlí, velikost má spodní mez. */
export function setNote(graph: FlowGraph, id: string, patch: Partial<Omit<FlowNote, "id">>): FlowGraph {
  const round = (value: number | undefined, min = -Infinity) => value === undefined ? undefined : Math.max(min, Math.round(value));
  return { ...graph, notes: (graph.notes ?? []).map((note) => note.id !== id ? note : { ...note, ...patch,
    x: round(patch.x) ?? note.x, y: round(patch.y) ?? note.y, width: round(patch.width, 80) ?? note.width, height: round(patch.height, 60) ?? note.height }) };
}

export const removeNote = (graph: FlowGraph, id: string): FlowGraph => ({ ...graph, notes: (graph.notes ?? []).filter((note) => note.id !== id) });

/** Rámec z vybraných uzlů; uzel už v jiném rámci nebo méně než dva uzly = chyba s důvodem. */
export function groupFromSelection(graph: FlowGraph, nodeIds: readonly string[], name = "Rámec"): { graph: FlowGraph; group: FlowGroup } {
  const ids = nodeIds.filter((id) => graph.nodes.some((node) => node.id === id));
  if (ids.length < 2) throw new Error("Rámec potřebuje aspoň dva vybrané uzly.");
  const groups = graph.groups ?? [];
  const taken = ids.find((id) => groups.some((group) => group.nodeIds.includes(id)));
  if (taken) throw new Error(`Uzel ${taken} už je v jiném rámci.`);
  const group: FlowGroup = { id: nextId("ramec", groups), name, description: "", nodeIds: ids };
  return { graph: { ...graph, groups: [...groups, group] }, group };
}

/** Jméno a popis rámce; popis má jako n8n nejvýš 145 znaků. */
export function setGroup(graph: FlowGraph, id: string, patch: Partial<Pick<FlowGroup, "name" | "description">>): FlowGraph {
  const description = patch.description?.slice(0, 145);
  return { ...graph, groups: (graph.groups ?? []).map((group) => group.id !== id ? group : { ...group, ...patch, ...(description !== undefined ? { description } : {}) }) };
}

/** Rozpustí rámec, uzly zůstanou. */
export const ungroup = (graph: FlowGraph, id: string): FlowGraph => ({ ...graph, groups: (graph.groups ?? []).filter((group) => group.id !== id) });
