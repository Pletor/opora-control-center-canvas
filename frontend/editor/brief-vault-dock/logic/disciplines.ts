// Disciplíny (neurony) Schránky, zrcadlo `backend/editor/brief_vault/brief_vault_disciplines.py`
// (docs/schranka-neurony.md §2; test hlídá shodu). Přepínač disciplín je jen filtr pohledu: strom se zúží na
// fragmenty s platnou disciplínou (`effectiveDiscipline`) a předci jiné disciplíny zůstanou jako cesta ke kořeni
// (`offPath`), aby strom zůstal souvislý. Poslední volba se pamatuje jednou pro aplikaci. Bez Reactu.
import { coverageOf, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";

export type DisciplineGroup = "kresleni" | "logika" | "provoz";
export type Discipline = { id: string; group: DisciplineGroup; label: string; layer: "frontend" | "backend" | "database" | null; logicBlocks: boolean };

export const GROUPS: { id: DisciplineGroup; label: string }[] = [
  { id: "kresleni", label: "Kreslení" },
  { id: "logika", label: "Logika" },
  { id: "provoz", label: "Provoz" },
];

export const DISCIPLINES: Discipline[] = [
  { id: "cx", group: "kresleni", label: "CX (zkušenost zákazníka)", layer: "frontend", logicBlocks: false },
  { id: "ux", group: "kresleni", label: "UX (tok, obrazovky, stavy)", layer: "frontend", logicBlocks: false },
  { id: "ui", group: "kresleni", label: "UI (vzhled, komponenty)", layer: "frontend", logicBlocks: false },
  { id: "content", group: "kresleni", label: "Obsah a texty", layer: "frontend", logicBlocks: false },
  { id: "fe", group: "logika", label: "Frontend (implementace)", layer: "frontend", logicBlocks: false },
  { id: "be", group: "logika", label: "Backend", layer: "backend", logicBlocks: true },
  { id: "api", group: "logika", label: "API a kontrakty", layer: "backend", logicBlocks: true },
  { id: "db", group: "logika", label: "Databáze a datový model", layer: "database", logicBlocks: true },
  { id: "cache", group: "logika", label: "Cache", layer: "database", logicBlocks: true },
  { id: "ai", group: "logika", label: "AI a agenti (retrieval, paměť, routing)", layer: "backend", logicBlocks: true },
  { id: "security", group: "logika", label: "Bezpečnost a soukromí", layer: "backend", logicBlocks: true },
  { id: "data", group: "logika", label: "Data a analytika", layer: "backend", logicBlocks: true },
  { id: "test", group: "logika", label: "Testy, QA, evaly", layer: "backend", logicBlocks: false },
  { id: "infra", group: "provoz", label: "Infrastruktura", layer: null, logicBlocks: false },
  { id: "cloud", group: "provoz", label: "Cloud", layer: null, logicBlocks: false },
  { id: "devops", group: "provoz", label: "CI/CD a nasazení", layer: null, logicBlocks: false },
  { id: "observability", group: "provoz", label: "Logy, metriky, trasování", layer: null, logicBlocks: false },
];

/** Pohled přepínače: id disciplíny, nebo `none` = nezařazené (bez disciplíny na celé cestě ke kořeni). */
export type DisciplineView = string;
export const UNASSIGNED = "none";
const BY_ID = new Map(DISCIPLINES.map((item) => [item.id, item]));
export const isDiscipline = (value: unknown): value is string => typeof value === "string" && BY_ID.has(value);

/** Krátký popisek do přepínače a drobečků; `none` = „Nezařazené“. */
export const disciplineLabel = (view: DisciplineView): string => (view === UNASSIGNED ? "Nezařazené" : BY_ID.get(view)?.label ?? view);
export const groupLabel = (view: DisciplineView): string => GROUPS.find((group) => group.id === BY_ID.get(view)?.group)?.label ?? "";

/** Platná disciplína uzlu podle serveru (`effectiveDiscipline`), jinak nezařazené. */
export const viewOf = (node: Pick<VaultNode, "effectiveDiscipline">): DisciplineView =>
  isDiscipline(node.effectiveDiscipline) ? node.effectiveDiscipline : UNASSIGNED;

/** Strom jedné disciplíny: shoda zůstane celá se svými shodnými potomky, předek jiné disciplíny jen jako cesta (`offPath`). */
export function filterByDiscipline(roots: VaultNode[], view: DisciplineView): VaultNode[] {
  const keep = (node: VaultNode): VaultNode | null => {
    const children = node.children.map(keep).filter((child): child is VaultNode => !!child);
    if (viewOf(node) === view) return { ...node, offPath: false, children };
    return children.length ? { ...node, offPath: true, children } : null;
  };
  return roots.map(keep).filter((root): root is VaultNode => !!root);
}

/** Počet živých fragmentů druhu `brief` podle platné disciplíny v rozsahu (stejné pravidlo jako server `live`). */
export function disciplineCounts(roots: VaultNode[]): Record<DisciplineView, number> {
  const counts: Record<DisciplineView, number> = { [UNASSIGNED]: 0 };
  const stack = [...roots];
  while (stack.length) {
    const node = stack.pop()!;
    if (node.kind === "brief") counts[viewOf(node)] = (counts[viewOf(node)] ?? 0) + 1;
    stack.push(...node.children);
  }
  return counts;
}

/** Zapnutý neuron = disciplína s živým fragmentem: na serveru (`live`) nebo v načteném stromu rozsahu. */
export type ServerDiscipline = Discipline & { live: number };
export function liveDisciplines(server: ServerDiscipline[] | undefined, local: Record<DisciplineView, number>): Discipline[] {
  const live = new Map((server ?? []).map((item) => [item.id, item.live]));
  return DISCIPLINES.filter((item) => (live.get(item.id) ?? 0) > 0 || (local[item.id] ?? 0) > 0);
}

/** Zobrazená disciplína: zapamatovaná, je-li zapnutá; jinak první zapnutá s obsahem v rozsahu; jinak nezařazené. */
export function pickDiscipline(stored: DisciplineView | null, live: Discipline[], local: Record<DisciplineView, number>): DisciplineView {
  if (stored === UNASSIGNED || (stored && live.some((item) => item.id === stored))) return stored;
  return live.find((item) => (local[item.id] ?? 0) > 0)?.id ?? live[0]?.id ?? UNASSIGNED;
}

/** Jediný klíč pro celou aplikaci. Nikdy se do něj nepřidává id projektu. */
export const VAULT_DISCIPLINE_KEY = "opora:vault-discipline:v1";
/** Klíč z doby dvou stop; čte se jen jednou při migraci (ux → ux, logic → be, none → none) a smaže se. */
export const LEGACY_VIEW_KEY = "opora:vault-track:v1";
const LEGACY_VIEWS: Record<string, DisciplineView> = { ux: "ux", logic: "be", none: UNASSIGNED };

/** Uložená volba je cizí text: neznámá hodnota nebo rozbitý JSON znamená „žádná“. */
export function parseDiscipline(raw: string | null): DisciplineView | null {
  try {
    const value = raw ? (JSON.parse(raw) as { discipline?: unknown } | null)?.discipline : null;
    return value === UNASSIGNED || isDiscipline(value) ? value : null;
  } catch {
    return null;
  }
}

/** Stará volba stopy → disciplína (`{"track":"logic"}` → `be`); cokoli jiného `null`. */
export function migrateLegacy(raw: string | null): DisciplineView | null {
  try {
    const value = raw ? (JSON.parse(raw) as Record<string, unknown> | null)?.["track"] : null;
    return typeof value === "string" ? LEGACY_VIEWS[value] ?? null : null;
  } catch {
    return null;
  }
}

export function readDiscipline(): DisciplineView | null {
  try {
    const current = parseDiscipline(localStorage.getItem(VAULT_DISCIPLINE_KEY));
    if (current) return current;
    const migrated = migrateLegacy(localStorage.getItem(LEGACY_VIEW_KEY));
    localStorage.removeItem(LEGACY_VIEW_KEY);
    if (migrated) writeDiscipline(migrated);
    return migrated;
  } catch {
    return null;
  }
}

export function writeDiscipline(discipline: DisciplineView): void {
  try { localStorage.setItem(VAULT_DISCIPLINE_KEY, JSON.stringify({ discipline })); } catch { /* bez úložiště jen v paměti */ }
}

/**
 * Kam patří fragment z Podnětu: pod kořen vybrané disciplíny (zdědí ji; kořen jiné disciplíny je v pohledu jen
 * cesta), jinak nový kořen s disciplínou. Nový kořen bez disciplíny server odmítne, proto u „Nezařazené“ musí
 * disciplínu zvolit člověk (`chosen`); bez ní vrátí `null`.
 */
export function ideaTarget(roots: VaultNode[], vaultScope: string, view: DisciplineView, chosen: string | null):
  { parentId: string } | { scopeNodeId: string; discipline: string } | null {
  const root = roots.find((item) => !item.offPath);
  if (root) return { parentId: root.id };
  const discipline = view === UNASSIGNED ? chosen : view;
  return discipline && isDiscipline(discipline) ? { scopeNodeId: vaultScope, discipline } : null;
}
