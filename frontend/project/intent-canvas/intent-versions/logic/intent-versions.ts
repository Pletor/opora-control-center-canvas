// Verze záměru stránky jako tři místa na liště: aktivní (schválený záměr, podle kterého srdce plánuje), kandidát
// (čeká na schválení člověkem) a rozpracovaný draft novější než oba. Rozdíl proti aktivní verzi se počítá v uzlech:
// kolik kritérií a kroků přibylo, ubylo a změnilo se.
import type { FlowGraph, FlowVersion, VersionStatus } from "@/shared/flow-editor/logic/flow-types";
import { graphDiff, type GraphDiff, type NodeMark } from "@/shared/flow-editor/logic/graph-diff";

export type IntentLane = { active: FlowVersion | null; candidate: FlowVersion | null; draft: FlowVersion | null };
export type DiffCounts = Record<NodeMark, number>;
export const EMPTY_GRAPH: FlowGraph = { nodes: [], edges: [] };

export function intentLane(versions: readonly FlowVersion[]): IntentLane {
  const newest = (status: VersionStatus) => versions.filter((item) => item.status === status).sort((a, b) => b.n - a.n)[0] ?? null;
  const active = newest("active"), candidate = newest("candidate"), draft = newest("draft");
  return { active, candidate, draft: draft && draft.n > Math.max(active?.n ?? 0, candidate?.n ?? 0) ? draft : null };
}

/** Zobrazená verze: vybraná, jinak kandidát (ten čeká na člověka), jinak rozpracovaný draft, jinak aktivní, jinak
 * nejnovější (třeba zamítnutý kandidát, ze kterého jde začít znovu). */
export function pickIntentVersion(versions: readonly FlowVersion[], lane: IntentLane, wanted: string | null): FlowVersion | null {
  return versions.find((item) => item.id === wanted) ?? lane.candidate ?? lane.draft ?? lane.active ?? versions.at(-1) ?? null;
}

/** Rozdíl zobrazeného grafu proti aktivní verzi (bez aktivní proti prázdnému grafu); u neupravené aktivní verze nic. */
export function diffToActive(lane: IntentLane, viewing: FlowVersion | null, graph: FlowGraph): GraphDiff | null {
  if (viewing && viewing.id === lane.active?.id && graph === viewing.graph) return null;
  return graphDiff(lane.active?.graph ?? EMPTY_GRAPH, graph);
}

export function diffCounts(diff: GraphDiff): DiffCounts {
  const counts: DiffCounts = { added: 0, removed: 0, changed: 0 };
  for (const mark of diff.nodes.values()) counts[mark] += 1;
  return counts;
}

export const diffText = ({ added, removed, changed }: DiffCounts) => `+${added} přidáno · −${removed} odebráno · ~${changed} změněno`;
