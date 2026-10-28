// Záznam činnosti bez Reactu: tvar odpovědi `GET /api/activity-log` (docs/zaznam-cinnosti.md),
// lidský popis akce z cesty, čas, dny, stav a jména karet. Komponenty jen mapují výsledek na JSX.

export type Actor = "human" | "agent";

/** Jeden zápis, jak ho vrací backend (nejnovější první). */
export type ActivityEntry = {
  id: number;
  at: string;
  actor: Actor;
  agent: string;
  method: string;
  path: string;
  project: string;
  workspace: string;
  nodeIds: string[];
  status: number;
  summary: string;
  /** `"full"` = agent to smí jen díky plné autonomii projektu (docs/plna-autonomie-agenta.md §2). */
  autonomy?: "full";
};

export type ActivityPage = { entries: ActivityEntry[]; nextBefore: number | null };

/** Popisky cest; delší předpona vyhrává (`/api/canvas-versions/restore` před `/api/canvas-versions`). */
const ACTION_LABELS: Record<string, string> = {
  "/api/desktop-v3/agent-output": "Výstup agenta",
  "/api/desktop-v3/agent-workspace": "Prostor agenta",
  "/api/desktop-v3/block": "Blok karty",
  "/api/desktop-v3/node": "Stav karty",
  "/api/desktop-v3/state": "Stav karet",
  "/api/node-spec": "Zadání karty",
  "/api/node-text": "Text karty",
  "/api/graph": "Plátno (graf)",
  "/api/canvas-plan": "Dávka plánu",
  "/api/canvas-versions/restore": "Obnova verze",
  "/api/canvas-versions": "Uložit vše",
};
const PREFIXES = Object.keys(ACTION_LABELS).sort((a, b) => b.length - a.length);

/** Krátký lidský název akce z cesty; neznámá cesta zůstane cestou. */
export function actionLabel(path: string): string {
  const clean = path.split("?")[0];
  const hit = PREFIXES.find((prefix) => clean === prefix || clean.startsWith(prefix + "/"));
  return hit ? ACTION_LABELS[hit] : clean;
}

/**
 * Doplněk akce ze `summary`: druh operace a návrh uzavření. Seznam klíčů těla (první část) se
 * neukazuje — je to technický údaj, patří do tooltipu.
 */
export function summaryDetail(summary: string): string {
  const parts: string[] = [];
  for (const token of summary.split(" ")) {
    if (token.startsWith("op=") && token.length > 3) parts.push(token.slice(3));
    if (token === "done.proposed=true") parts.push("návrh uzavření");
  }
  return parts.join(" · ");
}

/** Akci provedl agent díky plné autonomii projektu; řádek dostane štítek „plná autonomie“. */
export function isFullAutonomy(entry: Pick<ActivityEntry, "autonomy">): boolean {
  return entry.autonomy === "full";
}

/** Zápis selhal, když status není 2xx (včetně 0 = žádná odpověď). */
export function isFailed(status: number): boolean {
  return !(status >= 200 && status < 300);
}

const pad = (value: number) => String(value).padStart(2, "0");

/** Místní čas „HH:MM“; neplatný čas = prázdný řetězec. */
export function timeLabel(at: string): string {
  const date = new Date(at);
  return Number.isNaN(date.getTime()) ? "" : `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Klíč místního dne `YYYY-MM-DD`; neplatný čas = „?“. */
export function dayKey(at: string | Date): string {
  const date = new Date(at);
  if (Number.isNaN(date.getTime())) return "?";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Nadpis dne: Dnes, Včera, jinak „6. 10. 2026“. */
export function dayLabel(key: string, now: Date = new Date()): string {
  if (key === "?") return "Neznámý čas";
  if (key === dayKey(now)) return "Dnes";
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  if (key === dayKey(yesterday)) return "Včera";
  const [year, month, day] = key.split("-").map(Number);
  return `${day}. ${month}. ${year}`;
}

export type DayGroup = { key: string; label: string; entries: ActivityEntry[] };

/** Zápisy po dnech v pořadí, v jakém přišly (nejnovější den první). */
export function groupByDay(entries: ActivityEntry[], now: Date = new Date()): DayGroup[] {
  const groups: DayGroup[] = [];
  for (const entry of entries) {
    const key = dayKey(entry.at);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.entries.push(entry);
    else groups.push({ key, label: dayLabel(key, now), entries: [entry] });
  }
  return groups;
}

export type NodeRef = { id: string; name: string; known: boolean };

/** Jména karet z grafu plátna; karta mimo graf (smazaná, jiná vrstva dat) zůstane svým ID. */
export function nodeRefs(ids: string[], nodes: { id: string; name: string }[]): NodeRef[] {
  const names = new Map(nodes.map((node) => [node.id, node.name]));
  return ids.map((id) => {
    const name = names.get(id);
    return { id, name: name?.trim() || id, known: name !== undefined };
  });
}

/** Dotaz na jednu stránku záznamu jednoho aktéra. */
export function activityQuery(scope: { project: string; workspace: string; actor: Actor; nodeId?: string | null; before?: number | null; limit?: number }): string {
  const params = new URLSearchParams({ project: scope.project, workspace: scope.workspace, actor: scope.actor, limit: String(scope.limit ?? 100) });
  if (scope.nodeId) params.set("nodeId", scope.nodeId);
  if (scope.before != null) params.set("before", String(scope.before));
  return "/api/activity-log?" + params.toString();
}

/**
 * Obnovená první stránka se přiloží k už načteným: nic se nezdvojí, pořadí zůstane nejnovější
 * první. Když se nová stránka s načtenými překrývá, platí dosavadní `nextBefore` (starší stránky
 * už jsou načtené); když je mezi nimi mezera, začíná se znovu od nové stránky.
 */
export function mergeFresh(previous: ActivityPage, fresh: ActivityPage): ActivityPage {
  if (previous.entries.length === 0 || fresh.entries.length === 0) return fresh;
  const newestKnown = previous.entries[0].id;
  const oldestFresh = fresh.entries[fresh.entries.length - 1].id;
  if (oldestFresh > newestKnown && fresh.nextBefore !== null) return fresh;
  const byId = new Map<number, ActivityEntry>();
  for (const entry of [...fresh.entries, ...previous.entries]) if (!byId.has(entry.id)) byId.set(entry.id, entry);
  return { entries: [...byId.values()].sort((a, b) => b.id - a.id), nextBefore: previous.nextBefore };
}

/** Starší stránka se přidá na konec; další `before` je její. */
export function appendOlder(previous: ActivityPage, older: ActivityPage): ActivityPage {
  const known = new Set(previous.entries.map((entry) => entry.id));
  return { entries: [...previous.entries, ...older.entries.filter((entry) => !known.has(entry.id))], nextBefore: older.nextBefore };
}

export type TabStats = { count: string; failed: number };

/** Čísla na záložce: počet načtených (s „+“, když jsou další starší) a kolik z nich selhalo. */
export function tabStats(page: ActivityPage): TabStats {
  return {
    count: String(page.entries.length) + (page.nextBefore !== null ? "+" : ""),
    failed: page.entries.filter((entry) => isFailed(entry.status)).length,
  };
}
