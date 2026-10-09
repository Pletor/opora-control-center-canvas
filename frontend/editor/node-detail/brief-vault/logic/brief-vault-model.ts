// Čistý model schránky zadání (docs/navrh-schranka-zadani.md, „UI“). Tvary odpovídají
// GET /api/brief-vault a /api/brief-vault/fragment (backend/editor/brief_vault/brief_vault_tree.py).
// Stav fragmentu odvozuje server; tady se jen počítá pruh pokrytí, kulička stavu a „změněno po vložení“.

export type FragmentRef = { fragmentId: string; revision: number };
export type FragmentStatus = "changed" | "inserted" | "research" | "mvp" | "proposed" | "saved";
export type FragmentKind = "brief" | "research";

/** Revize fragmentu bez textu (`public()` na serveru). */
export type FragmentRevision = {
  id: string;
  revision: number;
  parentId: string | null;
  scopeNodeId: string | null;
  ord: number;
  kind: FragmentKind;
  title: string;
  stage: "draft" | "research" | "ready";
  mvp: "none" | "proposed" | "yes" | "no";
  note: string;
  by: string;
  actor: string;
  at: string;
  deleted: boolean;
  chars: number;
};

/** Uzel stromu schránky s odvozeným stavem; `children` jsou podfragmenty i research. */
export type VaultNode = FragmentRevision & {
  status: FragmentStatus;
  inserted: boolean;
  cards: { nodeId: string; revision: number }[];
  changedSinceInsert: boolean;
  /** Otevřené Podněty navázané na fragment. */
  ideas: number;
  children: VaultNode[];
};
export type VaultTree = { readOnly: boolean; roots: VaultNode[] };

export type FragmentDetail = {
  fragment: FragmentRevision & { text: string };
  latestRevision: number;
  history: FragmentRevision[];
  path: { id: string; title: string }[];
  scopeNodeId: string | null;
  status: FragmentStatus;
  children: (FragmentRevision & { status: FragmentStatus })[];
  cards: { nodeId: string; revision: number; changedSinceInsert: boolean }[];
  ideas: { nodeId: string; ideaId: string; text: string; status: "open" | "done" }[];
};

/** Segmenty pruhu pokrytí v pevném pořadí (zleva): hotové vlevo, varování vpravo. */
export type CoverageKey = "mvpInserted" | "inserted" | "research" | "saved" | "changed";
export const COVERAGE_SEGMENTS: { key: CoverageKey; label: string }[] = [
  { key: "mvpInserted", label: "MVP vloženo" },
  { key: "inserted", label: "vloženo" },
  { key: "research", label: "v researchu" },
  { key: "saved", label: "uloženo" },
  { key: "changed", label: "změněno" },
];
export type Coverage = Record<CoverageKey, number> & { leaves: number };

/** Kam patří list v pruhu: každý list právě do jednoho segmentu (součet = počet listů). */
export function coverageKey(node: Pick<VaultNode, "status" | "mvp">): CoverageKey {
  if (node.status === "changed") return "changed";
  if (node.status === "inserted") return node.mvp === "yes" ? "mvpInserted" : "inserted";
  if (node.status === "research") return "research";
  return "saved";
}

/**
 * Pokrytí stromu: počítají se listy druhu `brief` (research je poznámka k fragmentu, ne kus zadání).
 * Fragment, jehož jedinými dětmi jsou research, je list. Stejné pravidlo jako server (`tree_of`).
 */
export function coverageOf(roots: VaultNode[]): Coverage {
  const result: Coverage = { leaves: 0, mvpInserted: 0, inserted: 0, research: 0, saved: 0, changed: 0 };
  const walk = (node: VaultNode) => {
    if (node.kind !== "brief") return;
    const briefs = node.children.filter((child) => child.kind === "brief");
    if (!briefs.length) {
      result.leaves += 1;
      result[coverageKey(node)] += 1;
      return;
    }
    briefs.forEach(walk);
  };
  roots.forEach(walk);
  return result;
}

/** Šířky segmentů v procentech; prázdný strom = žádný segment. */
export function coverageSegments(coverage: Coverage): { key: CoverageKey; label: string; count: number; percent: number }[] {
  if (!coverage.leaves) return [];
  return COVERAGE_SEGMENTS.filter((segment) => coverage[segment.key] > 0)
    .map((segment) => ({ ...segment, count: coverage[segment.key], percent: (coverage[segment.key] / coverage.leaves) * 100 }));
}

/** Kulička stavu ve stromu: stejný vizuální jazyk jako porty karty (plná, poloviční, prázdná, varování). */
export type StatusDot = { tone: "mvp" | "inserted" | "research" | "proposed" | "saved" | "changed"; label: string };
export function statusDot(node: Pick<VaultNode, "status" | "mvp" | "kind" | "stage">): StatusDot {
  if (node.kind === "research") return node.stage === "ready"
    ? { tone: "saved", label: "research uzavřen" } : { tone: "research", label: "v researchu" };
  switch (node.status) {
    case "changed": return { tone: "changed", label: "změněno po vložení" };
    case "inserted": return node.mvp === "yes" ? { tone: "mvp", label: "MVP vloženo" } : { tone: "inserted", label: "vloženo" };
    case "research": return { tone: "research", label: "v researchu" };
    case "mvp": return { tone: "mvp", label: "MVP, nevloženo" };
    case "proposed": return { tone: "proposed", label: "návrh do MVP" };
    default: return { tone: "saved", label: "uloženo" };
  }
}

/** Plochý rejstřík stromu podle id (pro čipy karty a odznak „zadání se změnilo“). */
export function indexVault(roots: VaultNode[]): Map<string, VaultNode> {
  const index = new Map<string, VaultNode>();
  const walk = (node: VaultNode) => { index.set(node.id, node); node.children.forEach(walk); };
  roots.forEach(walk);
  return index;
}

export type BriefChip = { fragmentId: string; title: string; insertedRevision: number; latestRevision: number | null; changed: boolean };

/** Čipy „Ze schránky“ karty; fragment mimo načtený strom (smazaný, jiný prostor) zůstane jako „nedostupné“. */
export function briefChips(refs: FragmentRef[] | undefined, index: Map<string, VaultNode>): BriefChip[] {
  return (refs ?? []).map((ref) => {
    const node = index.get(ref.fragmentId);
    return { fragmentId: ref.fragmentId, title: node?.title ?? "nedostupné", insertedRevision: ref.revision,
      latestRevision: node?.revision ?? null, changed: !!node && ref.revision < node.revision };
  });
}

/** Kolik fragmentů karty má novější revizi, než ze které karta vznikla (0 = odznak se nekreslí). */
export function changedSinceInsert(refs: FragmentRef[] | undefined, index: Map<string, VaultNode>): number {
  return briefChips(refs, index).filter((chip) => chip.changed).length;
}

/** Karta má vlastní schránku, když některý kořen je připnutý k ní. */
export function hasOwnVault(roots: VaultNode[], nodeId: string): boolean {
  return roots.some((root) => root.scopeNodeId === nodeId);
}

/** Kořeny schránky jednoho rozsahu (`""` = plátno). */
export function rootsOf(roots: VaultNode[], scope: string): VaultNode[] {
  return roots.filter((root) => (root.scopeNodeId ?? "") === scope);
}

/** Krátký popis revize do historie: „r3 · agent · 9. 10. 17:50“. */
export function revisionLabel(item: Pick<FragmentRevision, "revision" | "by" | "at">): string {
  const at = new Date(item.at);
  const when = Number.isNaN(at.getTime()) ? item.at : at.toLocaleString("cs-CZ", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });
  return `r${item.revision} · ${item.by || "neznámý"} · ${when}`;
}
