import type { CanvasNode, NodeSite } from "@/shared/types/logic/types";

export type ProductDraft = { id?: string; original?: string; parentId: string | null; name: string; purpose: string; site: NodeSite };
export type ProductBranch = { node: CanvasNode; children: ProductBranch[] };

/** Ordinary canvas containers do not duplicate pages in the product navigation. */
export function productTree(nodes: CanvasNode[]): ProductBranch[] {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const branches = new Map(nodes.filter((node) => node.site).map((node) => [node.id, { node, children: [] } as ProductBranch]));
  const roots: ProductBranch[] = [];
  for (const branch of branches.values()) {
    if (branch.node.site?.kind === "application") { roots.push(branch); continue; }
    let parent = branch.node.parentId;
    const seen = new Set([branch.node.id]);
    let owner: ProductBranch | undefined;
    while (parent && !seen.has(parent)) {
      seen.add(parent);
      owner = branches.get(parent);
      if (owner) break;
      parent = byId.get(parent)?.parentId ?? null;
    }
    if (owner) owner.children.push(branch);
    else roots.push(branch);
  }
  return roots;
}

export function sitePlan(draft: ProductDraft) {
  return { nodes: [{ ref: "component", kind: draft.site.kind === "application" ? "sector" : "node",
    parent: draft.parentId ? `@${draft.parentId}` : null, name: draft.name.trim(), purpose: draft.purpose.trim(), site: draft.site,
    ...(draft.site.kind === "page" ? { card: { layer: "frontend", status: "draft" } } : {}),
  }] };
}

export function editProductNode(node: CanvasNode, draft: ProductDraft): CanvasNode {
  if (!node.site || node.site.kind !== draft.site.kind || node.id !== draft.id) throw new Error("Část projektu se změnila. Obnovte strom.");
  if (draft.original !== productFingerprint(node)) throw new Error("Údaje této části se mezitím změnily. Rozepsaný formulář zůstává zachovaný; porovnejte strom, zrušte formulář a otevřete aktuální položku.");
  return { ...node, name: draft.name.trim(), purpose: draft.purpose.trim(), site: draft.site };
}

/** Compare only fields this form owns; moving cards or adding children is harmless. */
export function productFingerprint(node: Pick<CanvasNode, "name" | "purpose" | "site">): string {
  return JSON.stringify([node.name, node.purpose, node.site?.kind,
    node.site?.kind === "application" ? node.site.environments.map((env) => [env.name, env.host]) : node.site?.path]);
}
