// Souhrn práce agentů nad kapitolami módu Text (`docs/souhrn-prace-agentu.md`). Čistý model: z dětí
// vrstvy, rozbalených kapitol, levného souhrnu paměti a načtených briefů složí řádky tabulky, umí je
// filtrovat, řadit podle dalšího kroku a přeložit čas a počty do češtiny. Nic nenačítá ani neukládá.
// Chybějící údaj je přiznaná mezera („–“), nikdy nula: bez briefu se o komunikaci nic neví.
import type { OverviewModel, WorkState } from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import { SECTIONS } from "@/editor/node-detail/agent-workspace/logic/agent-workspace";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";

export type ChapterWork = { filled: number; by: "human" | "agent"; updatedAt: string };
export type OverviewEntry = { status: "loading" | "ready" | "error"; overview: OverviewModel | null };
export type SummaryKind = "node" | "sector" | "area";
export type SummaryRow = {
  nodeId: string; name: string; kind: SummaryKind; state: WorkState; filled: number;
  by: "human" | "agent"; updatedAt: string; entry: OverviewEntry | null; closed: boolean;
};

/** Stav práce z levného souhrnu: bez vyplněného pole je karta prázdná, jinak podle toho, kdo psal. */
export function workStateOf(work: ChapterWork | undefined): WorkState {
  if (!work || work.filled <= 0) return "empty";
  return work.by === "agent" ? "agent" : "human";
}

/**
 * Práce jedné karty: levný souhrn, a když ho karta ještě nemá, pak z načteného briefu. Bez obojího
 * `undefined` — neznámo, ne vymyšlená nula.
 */
export function chapterWork(
  nodeId: string,
  works: Record<string, ChapterWork>,
  overviews: Record<string, OverviewEntry>,
): ChapterWork | undefined {
  const cheap = works[nodeId];
  if (cheap) return cheap;
  const brief = overviews[nodeId]?.overview?.work;
  if (!brief) return undefined;
  return { filled: brief.filled, by: brief.state === "agent" ? "agent" : "human", updatedAt: brief.updatedAt };
}

/** Řádky souhrnu v pořadí dětí na plátně, jen pro rozbalené kapitoly a bez komentářů. */
export function summaryRows(
  children: CanvasNode[],
  expanded: ReadonlySet<string>,
  works: Record<string, ChapterWork>,
  overviews: Record<string, OverviewEntry>,
  isClosed: (id: string) => boolean,
): SummaryRow[] {
  const rows: SummaryRow[] = [];
  for (const node of children) {
    if (node.kind === "comment" || !expanded.has(node.id)) continue;
    const entry = overviews[node.id] ?? null;
    const work = chapterWork(node.id, works, overviews);
    rows.push({
      nodeId: node.id, name: node.name, kind: node.kind, state: workStateOf(work),
      filled: work?.filled ?? 0, by: work?.by ?? "human", updatedAt: work?.updatedAt ?? "",
      entry, closed: isClosed(node.id),
    });
  }
  return rows;
}

/** Kolik věcí v komunikaci čeká na člověka. Nedostupná komunikace nemá počty, proto 0. */
export function pendingCount(overview: OverviewModel | null): number {
  if (!overview || !overview.communication.available) return 0;
  const { awaitingReceipt, needsClarification, openQuestions } = overview.communication;
  return awaitingReceipt + needsClarification + openQuestions;
}

/** Zamčený řádek: uzavřená karta, nebo brief hlásí důvod, proč je zápis zakázaný. */
export function isRowLocked(row: SummaryRow): boolean {
  return row.closed || (row.entry?.overview?.readOnlyReason ?? null) !== null;
}

export type SummaryFilter = "all" | "waiting" | "agent" | "human" | "empty" | "locked";
export const SUMMARY_FILTERS: { key: SummaryFilter; label: string }[] = [
  { key: "all", label: "Vše" },
  { key: "waiting", label: "Čeká na mě" },
  { key: "agent", label: "Agent" },
  { key: "human", label: "Člověk" },
  { key: "empty", label: "Prázdné" },
  { key: "locked", label: "Zamčené" },
];

export function filterRows(rows: SummaryRow[], filter: SummaryFilter): SummaryRow[] {
  switch (filter) {
    case "waiting": return rows.filter((row) => pendingCount(row.entry?.overview ?? null) > 0);
    case "agent":
    case "human":
    case "empty": return rows.filter((row) => row.state === filter);
    case "locked": return rows.filter(isRowLocked);
    default: return rows.slice();
  }
}

export type SummarySort = "canvas" | "next";

/** Naléhavost dalšího kroku: 0 chybí cíl … 4 ostatní (i bez briefu), 5 zamčené na konec. */
export function nextRank(row: SummaryRow): number {
  if (isRowLocked(row)) return 5;
  const overview = row.entry?.overview ?? null;
  if (!overview) return 4;
  if (overview.verification.goal === "missing") return 0;
  if (overview.verification.dod === "missing") return 1;
  if (overview.verification.gaps > 0) return 2;
  if (pendingCount(overview) > 0) return 3;
  return 4;
}

/** Stabilní řazení: stejně naléhavé řádky si drží pořadí z plátna. */
export function sortRows(rows: SummaryRow[], sort: SummarySort): SummaryRow[] {
  if (sort !== "next") return rows.slice();
  return rows
    .map((row, index) => ({ row, index, rank: nextRank(row) }))
    .sort((a, b) => a.rank - b.rank || a.index - b.index)
    .map((item) => item.row);
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** Čas změny řečí člověka; prázdné nebo neplatné datum je „–“. */
export function relativeTime(iso: string, now: Date): string {
  if (!iso) return "–";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "–";
  const diff = now.getTime() - date.getTime();
  if (diff < MINUTE) return "právě teď";
  if (diff < HOUR) return `před ${Math.floor(diff / MINUTE)} min`;
  if (diff < DAY) return `před ${Math.floor(diff / HOUR)} h`;
  if (diff < 2 * DAY) return "včera";
  if (diff < 7 * DAY) {
    const days = Math.floor(diff / DAY);
    return `před ${days} ${days <= 4 ? "dny" : "dní"}`;
  }
  return `${date.getDate()}. ${date.getMonth() + 1}. ${date.getFullYear()}`;
}

export function actorLabel(by: "human" | "agent"): string {
  return by === "agent" ? "agent" : "člověk";
}

const NEXT_ACTION_ICONS: Record<string, IconName> = {
  "request-context": "target",
  "follow-harness": "play",
  "read-only": "lock",
};

export function nextActionIcon(kind: string): IconName {
  return NEXT_ACTION_ICONS[kind] ?? "arrow-right";
}

/** Popisek teček paměti; které pole je vyplněné, levný souhrn neví, proto vyjmenuje všech pět. */
export function memoryTitle(filled: number): string {
  const count = Math.max(0, Math.min(SECTIONS.length, Math.floor(filled)));
  return `Paměť: vyplněno ${count} z ${SECTIONS.length} polí (${SECTIONS.map((section) => section.label).join(", ")})`;
}

/** České tvary podle počtu: 1 → one, 2–4 → few, jinak many (i 0). */
export function plural(count: number, one: string, few: string, many: string): string {
  if (count === 1) return one;
  if (count >= 2 && count <= 4) return few;
  return many;
}

export function gapsLabel(gaps: number): string {
  return `${gaps} ${plural(gaps, "mezera", "mezery", "mezer")}`;
}

/** Podtitul souhrnu: „3 rozbalené karty · 1 čeká na tebe“. */
export function summaryHeadline(expandedCount: number, waitingCount: number): string {
  const cards = `${expandedCount} ${plural(expandedCount, "rozbalená karta", "rozbalené karty", "rozbalených karet")}`;
  const waiting = waitingCount > 0 ? `${waitingCount} ${plural(waitingCount, "čeká", "čekají", "čeká")} na tebe` : "nic na tebe nečeká";
  return `${cards} · ${waiting}`;
}
