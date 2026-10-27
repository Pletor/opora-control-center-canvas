// Kontext karty podle docs/kontext-karet-a-index.md §1 a §3: typ workflow z předpony, vrstva, efektivní stav, čitelná cesta
// a adresa. Nic se tu neukládá; adresa se počítá z aktuálních názvů, takže přejmenování nebo přesun
// ji přepočítá sám. Backend drží tytéž funkce v `backend/canvas/card_context.py` se stejnými testy.
import type { CanvasNode, CardAgentFields, CardComponentFields, CardEffort, CardLayer, CardModel, CardStatus, CardType, NodeCardFields } from "@/shared/types/logic/types";

const WORKFLOW_TYPES: CardType[] = ["research", "prototype", "grilling", "task", "gate"];
export const CARD_LAYERS: CardLayer[] = ["frontend", "backend", "database", "library"];
/** Krátký štítek vrstvy: v čipech pop-upu, v detailu i v hlavě karty (stejně jako backend `LAYER_LABELS`). */
export const LAYER_LABEL: Record<CardLayer, string> = { frontend: "FE", backend: "BE", database: "DB", library: "Knihovna" };
export const CARD_STATUSES: CardStatus[] = ["draft", "ready"];
export const CARD_MODELS: CardModel[] = ["fable", "opus", "sonnet", "haiku"];
export const CARD_EFFORTS: CardEffort[] = ["low", "medium", "high", "xhigh", "max"];

/** Efektivní stav: `done` jen z uzavření karty, jinak ruční stav, jinak neznámo (`null`, ne „draft“). */
export type EffectiveStatus = CardStatus | "done";

type NamedNode = Pick<CanvasNode, "name"> & { card?: NodeCardFields & CardComponentFields };
type TreeNode = Pick<CanvasNode, "id" | "name" | "parentId">;

/** Předpona typu v názvu: přesně `[task] ` (malými písmeny, s mezerou); název se jí nemění. */
function prefixType(name: string): CardType | null {
  return WORKFLOW_TYPES.find((type) => name.startsWith(`[${type}] `)) ?? null;
}

/**
 * Typ workflow: jen předpona v názvu, jinak `null`; neukládá se. Stejně jako `effective_type`
 * v backendu se nedívá na druh, takže obě strany dávají pro tentýž graf tentýž výsledek.
 */
export function effectiveType(node: Pick<NamedNode, "name">): CardType | null {
  return prefixType(node.name);
}

/** Vrstva karty: platná uložená `card.layer`, jinak `null`. */
export function cardLayer(node: Pick<NamedNode, "card">): CardLayer | null {
  const stored = node.card?.layer;
  return stored && CARD_LAYERS.includes(stored) ? stored : null;
}

/** Stav karty: `done`, když je karta uzavřená (`done.confirmed`); jinak `card.status`; jinak `null`. */
export function effectiveStatus(node: Pick<NamedNode, "card">, doneConfirmed: boolean): EffectiveStatus | null {
  if (doneConfirmed) return "done";
  return node.card?.status || null;
}

/**
 * Slug názvu: předpona typu pryč, bez diakritiky, malá písmena, cokoli mimo `[a-z0-9]` → `-`,
 * sloučené a oříznuté pomlčky. Prázdný slug → `fallback` (id karty).
 */
export function slug(name: string, fallback = ""): string {
  const type = prefixType(name);
  const bare = type ? name.slice(type.length + 3) : name;
  const value = bare
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return value || fallback;
}

/** Předci karty od kořene a karta sama; kruh v datech se usekne, aby se adresa nezacyklila. */
function lineage(nodes: TreeNode[], node: TreeNode): TreeNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const chain: TreeNode[] = [node];
  const seen = new Set<string>([node.id]);
  let current = node.parentId ? byId.get(node.parentId) : undefined;
  while (current && !seen.has(current.id)) {
    seen.add(current.id);
    chain.unshift(current);
    current = current.parentId ? byId.get(current.parentId) : undefined;
  }
  return chain;
}

/** Názvy předků a karty, např. `["Editor", "Pop-up tvorby"]`; zobrazení přes `formatPath`. */
export function cardPath(nodes: TreeNode[], node: TreeNode): string[] {
  return lineage(nodes, node).map((n) => n.name);
}

/** Slugy téže cesty spojené `/`, např. `editor/pop-up-tvorby`; nikdy se nepoužívá jako klíč. */
export function cardAddress(nodes: TreeNode[], node: TreeNode): string {
  return lineage(nodes, node).map((n) => slug(n.name, n.id)).join("/");
}

/** Cesta pro člověka: `Editor › Pop-up tvorby`. */
export const formatPath = (path: string[]): string => path.join(" › ");

/** Karta s vypuštěnými prázdnými klíči; prázdná karta je `undefined` a do uzlu se nedává. */
export function normalizeCard(card: Partial<Record<keyof NodeCardFields, string>> | undefined): NodeCardFields | undefined {
  if (!card) return undefined;
  const next: NodeCardFields = {};
  if (CARD_LAYERS.includes(card.layer as CardLayer)) next.layer = card.layer as CardLayer;
  if (CARD_STATUSES.includes(card.status as CardStatus)) next.status = card.status as CardStatus;
  if (card.due && /^\d{4}-\d{2}-\d{2}$/.test(card.due)) next.due = card.due;
  if (CARD_MODELS.includes(card.model as CardModel)) next.model = card.model as CardModel;
  if (CARD_EFFORTS.includes(card.effort as CardEffort)) next.effort = card.effort as CardEffort;
  return Object.keys(next).length ? next : undefined;
}

/**
 * Komponenta karty (docs/architektura-pro-agenty.md §3.3): technologie, stavy a sekce stránky, jak jsou zapsané.
 * Nezapsané je `null` / prázdný seznam; nic se nedoplňuje.
 */
export function cardComponent(node: { card?: CardComponentFields }): { tech: string | null; states: string[]; section: string | null } {
  return { tech: node.card?.tech || null, states: node.card?.states ?? [], section: node.card?.section || null };
}

/**
 * Uzel s novou kartou: prázdná karta klíč `card` z uzlu odstraní, ostatní pole zůstanou beze změny.
 * Technologii, stavy, sekci komponenty ani `fetch` / `fill` z knihovny nenese formulář karty, proto je člověkova úprava karty zachová.
 */
export function withCard<T extends { card?: NodeCardFields & CardComponentFields & CardAgentFields }>(node: T, card: Partial<Record<keyof NodeCardFields, string>> | undefined): T {
  const { card: old, ...rest } = node;
  const kept: CardComponentFields & CardAgentFields = {};
  if (old?.tech) kept.tech = old.tech;
  if (old?.states?.length) kept.states = old.states;
  if (old?.section) kept.section = old.section;
  // Podklady a díry z knihovny (docs/zive-zobrazeni-a-knihovna.md §5) formulář karty také nenese.
  if (old?.fetch) kept.fetch = old.fetch;
  if (old?.fill?.length) kept.fill = old.fill;
  const next = { ...normalizeCard(card), ...kept };
  return (Object.keys(next).length ? { ...rest, card: next } : rest) as T;
}

/**
 * Uzel s novou sekcí stránky v `card.section` (docs/architektura-pro-agenty.md §3.3); `null` sekci odebere.
 * Ostatní pole karty zůstanou; karta, která tím zůstane prázdná, se z uzlu vypustí.
 */
export function withCardSection<T extends { card?: NodeCardFields & CardComponentFields }>(node: T, section: string | null): T {
  const { card: old, ...rest } = node;
  const { section: _old, ...card } = old ?? {};
  const next = section ? { ...card, section } : card;
  return (Object.keys(next).length ? { ...rest, card: next } : rest) as T;
}
