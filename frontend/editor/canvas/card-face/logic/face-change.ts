// Stopa karty na tváři (docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md, B): odznak pořadí podle záměru
// a jedna tichá řádka „kdo · kdy · co“ z nejnovějšího zápisu záznamu činnosti, který kartu nese v `nodeIds`
// (`GET /api/activity-log/latest-by-node`, jeden dotaz na celé plátno). Čistá data a funkce bez Reactu.
import { actionLabel, dayKey, dayLabel, timeLabel } from "@/editor/canvas/activity-log/logic/activity-log";

/** Jeden záznam odpovědi `latest-by-node`. */
export type LatestChange = { at: string; actor: string; agent: string; label: string; path: string };
export type LatestByNode = Record<string, LatestChange>;
/** Co tvář ukáže: kdo (a jakého druhu), kdy (syrový čas, popisek počítá komponenta) a co. */
export type FaceChange = { at: string; who: string; whoKind: "heart" | "human" | "agent"; what: string };

/** Zápis mladší než 10 minut karta krátce ohlásí zábleskem obrysu. */
export const FRESH_MS = 10 * 60 * 1000;

/** Odznak pořadí `F·PP`: `302` → `3·02`, `1205` → `12·05`; bez pořadí nic. */
export function orderBadge(order: number | null | undefined): string | null {
  if (typeof order !== "number" || !Number.isSafeInteger(order) || order < 0) return null;
  return `${Math.floor(order / 100)}·${String(order % 100).padStart(2, "0")}`;
}

/** Kdo změnu udělal: srdce, člověk („Vy“), jinak čitelné jméno dělníka. */
export function changeWho(actor: string, agent: string): Pick<FaceChange, "who" | "whoKind"> {
  if (agent === "heart") return { who: "Srdce", whoKind: "heart" };
  if (actor === "human") return { who: "Vy", whoKind: "human" };
  const name = agent.replace(/^agent:/, "").trim();
  return { who: !name || name === "agent" ? "Agent" : "Dělník " + name, whoKind: "agent" };
}

/** Řádka poslední změny ze zápisu; bez zápisu nebo s neplatným časem nic. */
export function changeOf(entry: LatestChange | undefined): FaceChange | null {
  if (!entry || Number.isNaN(Date.parse(entry.at))) return null;
  return { at: entry.at, ...changeWho(entry.actor, entry.agent), what: entry.label.trim() || actionLabel(entry.path) };
}

/** Kdy krátce: dnes „HH:MM“, „včera“, letos „6. 10.“, jinak celé datum. */
export function changeWhen(at: string, now: Date = new Date()): string {
  const key = dayKey(at);
  if (key === "?") return "";
  if (key === dayKey(now)) return timeLabel(at);
  const label = dayLabel(key, now);
  if (label === "Včera") return "včera";
  return key.startsWith(String(now.getFullYear()) + "-") ? label.replace(/ \d{4}$/, "") : label;
}

/** Změna je čerstvá (mladší než `FRESH_MS`, ne z budoucnosti víc než minutu). */
export function isFresh(at: string, now: number): boolean {
  const age = now - Date.parse(at);
  return age < FRESH_MS && age > -60_000;
}

/** Dotaz na poslední změnu všech karet prostoru. */
export function latestQuery(project: string, workspace: string): string {
  return `/api/activity-log/latest-by-node?${new URLSearchParams({ project, workspace })}`;
}

const isText = (value: unknown): value is string => typeof value === "string";

/** Přísné čtení odpovědi: záznam bez času nebo s jiným tvarem se vynechá, ne zobrazí napůl. */
export function parseLatest(raw: unknown): LatestByNode {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const out: LatestByNode = {};
  for (const [nodeId, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!value || typeof value !== "object") continue;
    const item = value as Record<string, unknown>;
    if (!isText(item.at) || !isText(item.actor)) continue;
    out[nodeId] = { at: item.at, actor: item.actor, agent: isText(item.agent) ? item.agent : "",
      label: isText(item.label) ? item.label : "", path: isText(item.path) ? item.path : "" };
  }
  return out;
}
