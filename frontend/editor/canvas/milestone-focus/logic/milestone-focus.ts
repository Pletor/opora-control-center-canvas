import type { Node } from "@xyflow/react";
import type { Graph } from "@/shared/types/logic/types";
import type { IntakeResponse } from "@/editor/control-tower/intake-plan/logic/intake-plan";
import { parseBlockId } from "@/editor/workflow/blocks/logic/block-model";

export type MilestoneFocus = { id: string; title: string; area: string; cards: string[]; closure: number | null;
  verification?: { verified: boolean; independent?: boolean; source?: string; acceptedRevision?: string; headSha?: string } };

/** References come from the existing intake record, never a second milestone store. */
export function activeMilestones(data: IntakeResponse | null): MilestoneFocus[] {
  return (data?.areas ?? []).flatMap(area => {
    const milestone = area.milestone;
    if (!milestone || milestone.status !== "active") return [];
    const cards = [...new Set((milestone.criteria ?? []).flatMap(criterion =>
      (criterion.cards ?? []).map(card => typeof card === "string" ? card : card.id)))];
    const progress = milestone.closureProgress ?? milestone.progress;
    const closure = typeof progress === "number" && Number.isFinite(progress)
      ? Math.max(0, Math.min(100, Math.round(progress))) : null;
    return [{ id: milestone.id, title: milestone.title, area: area.name || area.id, cards, closure,
      ...(milestone.verification ? { verification: milestone.verification } : {}) }];
  });
}

/** Select branches leading to referenced cards, and descendants of those cards. Ancestors do not pull in siblings. */
export function milestoneMembers(graph: Graph, cards: readonly string[]): ReadonlySet<string> {
  const nodes = new Map(graph.nodes.map(node => [node.id, node]));
  const children = new Map<string, string[]>();
  for (const node of graph.nodes) if (node.parentId) {
    const group = children.get(node.parentId) ?? [];
    group.push(node.id); children.set(node.parentId, group);
  }
  const related = new Set<string>();
  const descendants = new Set<string>();
  const pending = cards.filter(id => nodes.has(id));
  while (pending.length) {
    const id = pending.pop()!;
    if (descendants.has(id)) continue;
    descendants.add(id); related.add(id);
    pending.push(...children.get(id) ?? []);
  }
  for (const seed of cards) {
    const path = new Set<string>();
    let id: string | null | undefined = seed;
    while (id && nodes.has(id) && !path.has(id)) {
      path.add(id); related.add(id); id = nodes.get(id)?.parentId;
    }
  }
  return related;
}

/** Focus is a visual projection: preserve IDs, positions, selection and access to every card. */
export function focusMilestoneNodes(nodes: Node[], members: ReadonlySet<string> | null): Node[] {
  if (!members) return nodes;
  return nodes.map(node => {
    const related = members.has(parseBlockId(node.id)?.nodeId ?? node.id);
    return { ...node, className: [node.className, related ? "milestone-focus__member" : "milestone-focus__outside"].filter(Boolean).join(" "),
      data: node.type === "canvas" ? { ...node.data, dimmed: !!node.data.dimmed || !related } : node.data };
  });
}
