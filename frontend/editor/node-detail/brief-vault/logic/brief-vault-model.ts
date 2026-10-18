// Čistý model schránky zadání (docs/navrh-schranka-zadani.md, „UI“). Tvary odpovídají
// GET /api/brief-vault a /api/brief-vault/fragment (backend/editor/brief_vault/brief_vault_tree.py).
// Stav fragmentu odvozuje server; tady se jen počítá pruh pokrytí, kulička stavu a „změněno po vložení“.

export type FragmentRef = { fragmentId: string; revision: number };
export type FragmentStatus = "changed" | "inserted" | "research" | "mvp" | "proposed" | "saved";
export type FragmentKind = "brief" | "research" | "question";
export type Verdict = "feasible" | "dead_end" | "unrealistic" | "unverified";
export type ResearchStatus = "assigned" | "running" | "done";
/** Výtah výzkumu ve stromu (bez důkazů). */
export type ResearchSummary = { question: string; verdict: Verdict; confidence: "" | "low" | "medium" | "high"; status: ResearchStatus; round: number; evidence: number };
export type QuestionSummary = { askedFor: "human" | "agent"; answered: boolean };

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
  /** Vlastní disciplína revize (`null` = dědí po předkovi; docs/schranka-neurony.md §2). Id z `brief-vault-dock/logic/disciplines.ts`. */
  discipline?: string | null;
};

/** Brány cyklu ve stromu a v detailu (docs/schranka-neurony.md §3): jen booleany a `predictionError` u `verified`. */
export type GateFlags = Record<GateName, boolean> & { predictionError: number | null };
export type GateName = "scoped" | "weighed" | "synthesized" | "decided" | "planned" | "placed" | "verified" | "learned";
/** Platná disciplína (nejbližší předek včetně sebe, `null` = nezařazené) a stav bran fragmentu. */
export type GateSummary = {
  effectiveDiscipline?: string | null;
  gates?: GateFlags;
  /** Počet platně zapnutých bran 0–8 (prefix v pořadí cyklu). */
  gateStep?: number;
  /** Některá zapnutá brána má jiný otisk vstupů (název, text, disciplína): chová se jako vypnutá. */
  gatesStale?: boolean;
  /** `decided` = `no`: slepá ulička. */
  deadEnd?: boolean;
  /** Kolo cyklu 1-3 (§11): každé vypnutí `synthesized` otevře další. */
  round?: number;
  /** Vyčerpaná kola (přes 3): fragment čeká na člověka, fronta agentů ho přeskakuje. */
  exhausted?: boolean;
};
/** Záznam brány v detailu fragmentu (`gateDetail`): payload, kdo a kdy, a zda platí. */
export type GateEntry = { value: boolean; payload: Record<string, unknown> | null; by: string; actor: string; at: string;
  inputHash: string; revision: number; valid: boolean };
/** Poslední návrh brány pro aktuální otisk vstupů (`proposals` v detailu): kdo navrhl a co se s návrhem stalo.
 *  `rejected` = zamítnutý op reject-proposal (`rejection` s autorem a poznámkou), nebo brána vypnutá po návrhu (`gateOff`). */
export type GateProposal = { id: string; revision: number; gate: GateName; payload: Record<string, unknown>; note: string;
  by: string; actor: string; at: string; status: "pending" | "rejected" | "used";
  rejection: { id: string | null; note: string; by: string; actor: string; at: string; gateOff?: boolean } | null };

/** Uzel stromu schránky s odvozeným stavem; `children` jsou podfragmenty, research i otázky. */
export type VaultNode = FragmentRevision & GateSummary & {
  status: FragmentStatus;
  inserted: boolean;
  cards: { nodeId: string; revision: number }[];
  /** Revize poslední změny TEXTU; „změněno po vložení“ porovnává jen s ní (metadata kartě zadání nemění). */
  textRevision?: number;
  changedSinceInsert: boolean;
  /** Otevřené Podněty navázané na fragment. */
  ideas: number;
  /** Počet záznamů zpětné vazby člověka. */
  feedback?: number;
  research?: ResearchSummary;
  question?: QuestionSummary;
  /** Id rozhodnutí plátna, na která fragment odkazuje (text se nekopíruje). */
  decisions?: string[];
  /** Kolik potomků pod stropem hloubky server už nevnořil. */
  hidden?: number;
  /** Pohled jedné disciplíny: uzel jiné disciplíny, který zůstal jen jako cesta ke kořeni (nepočítá se, nevkládá se). */
  offPath?: boolean;
  children: VaultNode[];
};
export type Feedback = { id: string; fragmentId: string; fragmentRevision: number; verdict: "agree" | "disagree" | "comment"; text: string; by: string; actor: string; at: string };
export type VaultTree = { readOnly: boolean; roots: VaultNode[]; feedback?: Feedback[] };
export type Evidence = { url: string; title: string; quote: string; accessedAt: string };
export type ResearchDetails = Omit<ResearchSummary, "evidence"> & { approach: string; evidence: Evidence[] };
export type QuestionDetails = { askedFor: "human" | "agent"; proposal: string; answer: string; answeredBy: string; answeredAt: string };

export type FragmentDetail = GateSummary & {
  fragment: FragmentRevision & { text: string };
  latestRevision: number;
  history: FragmentRevision[];
  path: { id: string; title: string }[];
  scopeNodeId: string | null;
  status: FragmentStatus;
  children: (FragmentRevision & { status: FragmentStatus })[];
  cards: { nodeId: string; revision: number; changedSinceInsert: boolean }[];
  ideas: { nodeId: string; ideaId: string; text: string; status: "open" | "done" }[];
  textRevision?: number;
  details?: { research?: ResearchDetails; question?: QuestionDetails; decisions?: string[] };
  decisions?: ({ id: string; available: true; text: string; nodeId: string; pinned: boolean } | { id: string; available: false })[];
  feedback?: Feedback[];
  /** Uložené záznamy bran (i vypnuté a zneplatněné) s payloadem; chybějící brána = nikdy nezapnutá. */
  gateDetail?: Partial<Record<GateName, GateEntry>>;
  /** Poslední návrh každé brány s payloadem pro aktuální otisk vstupů a jeho stav. */
  proposals?: Partial<Record<GateName, GateProposal>>;
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
      if (node.offPath) return;
      result.leaves += 1;
      result[coverageKey(node)] += 1;
      return;
    }
    briefs.forEach(walk);
  };
  roots.forEach(walk);
  return result;
}

/** Kolik listů v segmentu „změněno“ je zároveň MVP (potvrzené nebo navržené): varování MVP neschová. */
export function countChangedMvp(roots: VaultNode[]): number {
  let count = 0;
  const stack = [...roots];
  while (stack.length) {
    const node = stack.pop()!;
    if (node.kind !== "brief") continue;
    const briefs = node.children.filter((child) => child.kind === "brief");
    if (!briefs.length) { if (!node.offPath && node.status === "changed" && (node.mvp === "yes" || node.mvp === "proposed")) count += 1; }
    else stack.push(...briefs);
  }
  return count;
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
  if (node.kind === "question") return node.stage === "ready"
    ? { tone: "saved", label: "zodpovězeno" } : { tone: "proposed", label: "k upřesnění" };
  switch (node.status) {
    // Varování nesmí schovat MVP: kulička je žlutá, popisek i odznak řeknou, že jde o MVP.
    case "changed": return { tone: "changed", label: node.mvp === "yes" ? "MVP vloženo · změněno po vložení"
      : node.mvp === "proposed" ? "návrh MVP · změněno po vložení" : "změněno po vložení" };
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

/** Revize poslední změny textu (starší server bez `textRevision` = poslední revize). */
export function textRevisionOf(node: Pick<VaultNode, "revision" | "textRevision">): number {
  return node.textRevision ?? node.revision;
}

/** Čipy „Ze schránky“ karty; fragment mimo načtený strom (smazaný, jiný prostor) zůstane jako „nedostupné“. */
export function briefChips(refs: FragmentRef[] | undefined, index: Map<string, VaultNode>): BriefChip[] {
  return (refs ?? []).map((ref) => {
    const node = index.get(ref.fragmentId);
    const latest = node ? textRevisionOf(node) : null;
    return { fragmentId: ref.fragmentId, title: node?.title ?? "nedostupné", insertedRevision: ref.revision,
      latestRevision: latest, changed: latest != null && ref.revision < latest };
  });
}

/** Kolik fragmentů karty má novější TEXT, než ze kterého karta vznikla (0 = odznak se nekreslí). */
export function changedSinceInsert(refs: FragmentRef[] | undefined, index: Map<string, VaultNode>): number {
  return briefChips(refs, index).filter((chip) => chip.changed).length;
}

/** Rozsah schránky (vlastník kořene), ve které fragment leží; `null` = fragment mimo načtený strom. */
export function scopeOfFragment(index: Map<string, VaultNode>, fragmentId: string): string | null {
  let node = index.get(fragmentId);
  const seen = new Set<string>();
  while (node && node.parentId && !seen.has(node.id)) { seen.add(node.id); node = index.get(node.parentId); }
  return node && !node.parentId ? node.scopeNodeId ?? "" : null;
}

/** Druhy fragmentů, které nejsou zadání: duel o směr a představa (docs/schranka-duel.md); patří jen sekci Duel. */
export const NOT_BRIEF_KINDS: ReadonlySet<string> = new Set(["duel", "vision"]);

/** Karta má vlastní schránku, když k ní je připnutý kořen zadání (samotný duel nebo představa schránku nedělá). */
export function hasOwnVault(roots: VaultNode[], nodeId: string): boolean {
  return roots.some((root) => root.scopeNodeId === nodeId && !NOT_BRIEF_KINDS.has(root.kind as string));
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
