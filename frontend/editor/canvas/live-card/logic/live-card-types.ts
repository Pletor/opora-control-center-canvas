// Tvar `GET /api/oporahub/live-card` podle kontraktu K1 (docs/navrhy/2026-11-11-platno-3-folie.md).
// Každá sekce může být `null`; frontend ji pak nevykreslí. Parser hlídá jen kostru, ne každé pole.
import { isObject } from "@/hub/oporahub-mirror/logic/hub-read";

export type CardState = "seed" | "bud" | "leaf" | "dry" | "prop" | "goal";
export type PillTone = "work" | "real" | "risk" | "heart" | "vision";
export type ItemStatus = "ok" | "miss" | "bad" | "wait";
export type TruthItem = { text: string; status: ItemStatus };
export type Truth = { source: string; items: TruthItem[]; sha?: string };
export type PendingTruth = { available: false; milestone: string };
/** Zrcadlo kódu (F1): co z karty kód skutečně má. `ok` shoda, `miss` chybí, `bad` navíc nebo rozpor. */
export type MirrorItem = { kind: "file" | "symbol" | "route" | "test" | "output" | string; name: string; path: string;
  line?: number | null; status: "ok" | "miss" | "bad"; text: string };
export type MirrorTruth = { available: true; source: string; items: MirrorItem[];
  counts: { matched: number; missing: number; extra: number }; evidence: { commit: string; at: string } | null };
/** Budoucnost po sloučení (F4): co udělá sloučení otevřené práce karty. Bez otevřené práce sekce není. */
export type FutureVerdict = "clean" | "warning" | "blocked";
export type FutureImpact = { nodeId: string; name: string; via: string; paths: string[] };
export type FutureWork = { mark: string | null; branch: string; target: string; changed: string[]; conflicts: string[];
  impacts: FutureImpact[]; overlaps: { nodeId: string; mark: string | null; branch: string; paths: string[] }[] };
export type FutureTruth = { available: true; verdict: FutureVerdict | string; works: FutureWork[] };
export type LiveEdge = { edgeId: string; dir: "in" | "out"; relation: string | null; carries: string | null;
  other: { nodeId: string; title: string; state: CardState | string }; last: string | null };
export type LiveFlow = { source: string; pageId: string; elementId: string; name: string;
  inputs: unknown; steps: unknown; outputs: unknown; conditions: unknown; dataTo: unknown };
export type LiveOutput = { source: string; captures: { label: string; url: string }[]; preview: { url: string; status: string } | null };
export type LiveLinie = { source: string; ticketId: string; mark: string; branch: string; pr: string | number | null;
  axes: { name: string; state: string; text: string }[]; commits: { sha7: string; title: string }[]; gaps: string[] };
export type LiveRun = { executionId: string; at: string; state: string; tests: { passed: number; total: number } | null; costUsd: number | null };
export type RecentItem = { at: string; actor: string; kind: string; text: string; source: string };
export type LiveAgent = {
  address: string; lease: { holder: string; until: string } | null; revision: number | string | null;
  reads: { layer: string; method: "GET" | "SSE" | string; url: string; size: string | number | null; exists: boolean }[];
  writes: { role: string; method: string; url: string; what: string }[];
  triggers: { when: string; then: string }[];
};

export type LiveCard = {
  nodeId: string; title: string; kind: string; crumbs: string[]; state: CardState | string; progress: number | null;
  pills: { text: string; tone: PillTone | string }[];
  truths: { vision: Truth | null; mirror: MirrorTruth | PendingTruth | null; reality: Truth | null; future: FutureTruth | null };
  edges: LiveEdge[]; flow: LiveFlow | null; output: LiveOutput | null; linie: LiveLinie | null;
  runs: LiveRun[]; cost: { totalUsd: number | null; budgetUsd: number | null } | null;
  recent: RecentItem[]; decisions: { text: string; source: string }[];
  children: { nodeId: string; title: string; state: string; progress: number | null }[];
  next: { text: string; why: string } | null; heart: { at: string; severity: string | null; text: string } | null;
  agent: LiveAgent | null;
};

const list = <T>(value: unknown): T[] => Array.isArray(value) ? value as T[] : [];
const object = <T>(value: unknown): T | null => isObject(value) ? value as T : null;

const count = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value : 0;
/** Zrcadlo přijde buď hotové (`available: true`), nebo jako „staví se F1“; cokoli jiného se nekreslí. */
export function parseMirror(raw: unknown): MirrorTruth | PendingTruth | null {
  if (!isObject(raw)) return null;
  if (raw.available === false) return { available: false, milestone: String(raw.milestone ?? "F1") };
  if (raw.available !== true) return null;
  const counts = isObject(raw.counts) ? raw.counts : {};
  return { available: true, source: String(raw.source ?? ""),
    items: list<MirrorItem>(raw.items).filter(item => isObject(item) && typeof item.name === "string"),
    counts: { matched: count(counts.matched), missing: count(counts.missing), extra: count(counts.extra) },
    evidence: object(raw.evidence) };
}

/** Budoucnost jen hotová (`available: true`); `available: false` = karta nemá otevřenou práci, sekce se nekreslí. */
export function parseFuture(raw: unknown): FutureTruth | null {
  if (!isObject(raw) || raw.available !== true) return null;
  const works = list<FutureWork>(raw.works).filter(item => isObject(item) && typeof item.branch === "string")
    .map(item => ({ ...item, changed: list<string>(item.changed), conflicts: list<string>(item.conflicts),
      impacts: list<FutureImpact>(item.impacts), overlaps: list<FutureWork["overlaps"][number]>(item.overlaps) }));
  return { available: true, verdict: String(raw.verdict ?? "clean"), works };
}

/** Přísná kostra, volná pole: chybějící seznam je prázdný, chybějící sekce `null`. */
export function parseLiveCard(raw: unknown): LiveCard {
  if (!isObject(raw) || typeof raw.nodeId !== "string") throw new Error("Živá karta má neplatný tvar.");
  const truths = isObject(raw.truths) ? raw.truths : {};
  return {
    nodeId: raw.nodeId, title: typeof raw.title === "string" ? raw.title : raw.nodeId, kind: String(raw.kind ?? ""),
    crumbs: list<string>(raw.crumbs), state: String(raw.state ?? "seed"),
    progress: typeof raw.progress === "number" ? raw.progress : null, pills: list(raw.pills),
    truths: { vision: object(truths.vision), mirror: parseMirror(truths.mirror), reality: object(truths.reality), future: parseFuture(truths.future) },
    edges: list(raw.edges), flow: object(raw.flow), output: object(raw.output), linie: object(raw.linie),
    runs: list(raw.runs), cost: object(raw.cost), recent: list(raw.recent), decisions: list(raw.decisions),
    children: list(raw.children), next: object(raw.next), heart: object(raw.heart), agent: object(raw.agent),
  };
}

/** Odpověď node-brief se nevykládá: rub ukáže JSON tak, jak přišel. */
export const parseBrief = (raw: unknown): unknown => raw;
