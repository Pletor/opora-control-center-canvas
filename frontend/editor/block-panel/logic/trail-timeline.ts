// Jedna osa „Stopa práce“ (rozhodnutí člověka 2026-10-31, varianta 1a s relacemi a logem v jedné ose):
// relace dělníků a poslední změny karty se slijí podle času, nic se neukáže dvakrát. Rozbalená je jen
// nejnovější relace. Délka osy a rozbalení jsou nastavení aplikace (`TRAIL_SETTINGS`), nikdy ne projektu.
import { dayKey, dayLabel, timeLabel } from "@/editor/canvas/activity-log/logic/activity-log";
import type { CardTrail, TrailRecent, TrailRun, TrailSource } from "./card-trail";

/** Nastavení osy jednou pro celou aplikaci: nejvýš 10 položek, rozbalená jen poslední relace. */
export const TRAIL_SETTINGS = { limit: 10, expand: "last-run" as "last-run" | "none" };
export type TrailSettings = typeof TRAIL_SETTINGS;

/** Druhy událostí, které osa nekreslí: převzetí je už řádek relace, `tool.use` patří jen do řádky „teď“. */
const HIDDEN_KINDS = new Set(["lease.claimed", "lease.heartbeat", "tool.use"]);

export type SourceMark = { glyph: string; tone: TrailSource; title: string };
const MARKS: Record<TrailSource, SourceMark> = {
  det: { glyph: "⚙", tone: "det", title: "Odvozeno ze záznamů (bez modelu), lze věřit bez kontroly" },
  agent: { glyph: "A", tone: "agent", title: "Napsal dělník: jeho tvrzení, ne ověřený fakt" },
  heart: { glyph: "✦", tone: "heart", title: "Doplnilo srdce (úsudek modelu)" },
  human: { glyph: "H", tone: "human", title: "Napsal člověk" },
};
export const sourceMark = (source: TrailSource): SourceMark => MARKS[source];

/** Čitelné jméno aktéra: srdce, člověk, jinak jméno dělníka bez předpony `agent:`. */
export function whoName(who: string): { name: string; kind: "heart" | "human" | "agent" | "opora" } {
  const value = who.trim();
  if (value === "heart" || value === "agent:heart") return { name: "Srdce", kind: "heart" };
  if (value === "human") return { name: "Vy", kind: "human" };
  if (value === "opora") return { name: "OPORA", kind: "opora" };
  const name = value.replace(/^agent:/, "");
  return name && name !== "agent" ? { name, kind: "agent" } : { name: value ? "Agent" : "OPORA", kind: value ? "agent" : "opora" };
}

const RUN_STATE: Record<string, { word: string; tone: "live" | "ok" | "bad" | "idle" }> = {
  running: { word: "běží", tone: "live" }, assigned: { word: "přiděleno", tone: "live" }, ready: { word: "čeká", tone: "idle" },
  reported: { word: "doručeno", tone: "ok" }, done: { word: "hotovo", tone: "ok" }, released: { word: "uvolněno", tone: "idle" },
  expired: { word: "vypršelo", tone: "bad" }, revoked: { word: "odvoláno", tone: "bad" }, failed: { word: "selhalo", tone: "bad" },
  cancelled: { word: "zrušeno", tone: "idle" },
};
export const runState = (state: string) => RUN_STATE[state] ?? { word: state || "neznámý stav", tone: "idle" as const };

export type StepTone = "done" | "after" | "cur" | "bad" | "todo";
/** Značka kroku: ✓ hotovo, ↺ uznáno sloučením (krok přibyl po něm), ✗ selhalo, … rozpracováno, ○ čeká. */
export function stepMark(status: string, current = false): { glyph: string; tone: StepTone } {
  if (status === "done") return { glyph: "✓", tone: "done" };
  if (status === "after_merge") return { glyph: "↺", tone: "after" };
  if (status === "failed") return { glyph: "✗", tone: "bad" };
  if (current || status === "running" || status === "in_progress") return { glyph: "…", tone: "cur" };
  return { glyph: "○", tone: "todo" };
}

export type TimelineItem =
  | { kind: "run"; key: string; at: string; run: TrailRun; expanded: boolean }
  /** `count` > 1 = sbalená řada stejných událostí za sebou; `from` je čas nejstarší, `parts` co se v ní dělo. */
  | { kind: "event"; key: string; at: string; event: TrailRecent; count: number; from: string; parts: string[] };
export type TimelineGroup = { day: string; label: string; items: TimelineItem[] };

const moment = (at: string) => { const value = Date.parse(at); return Number.isNaN(value) ? 0 : value; };

/** Druhy, které patří k jednomu ději (kolo review se skládá z převzetí, odevzdání a čísla kola). */
const FAMILY: Record<string, string> = { "pr.review": "review", "review.round": "review" };
const family = (kind: string) => FAMILY[kind] ?? kind;

/** Společný začátek popisků po slovech („Review pletor/ample#40 (kolo 1)“); prázdný, když se liší hned první slovo. */
export function commonPrefix(labels: string[]): string {
  const words = labels.map((label) => label.trim().split(/\s+/));
  const first = words[0] ?? [];
  let size = 0;
  while (size < first.length && words.every((item) => item[size] === first[size])) size++;
  return first.slice(0, size).join(" ");
}

type EventBundle = { event: TrailRecent; count: number; from: string; parts: string[] };
/**
 * Opakované události stejného děje za sebou (např. osm řádků „Review … převzata / uvolněna / odevzdána“) sbalí
 * do jedné řádky: společný začátek popisku, počet a co se v ní dělo (od nejstaršího). Řada se sbalí jen když
 * popisky převažujícího druhu sdílejí začátek; „s1 hotovo“ a „s2 hotovo“ zůstanou samostatné kroky.
 */
export function bundleEvents(events: TrailRecent[]): EventBundle[] {
  const runs: TrailRecent[][] = [];
  for (const event of events) {
    const last = runs[runs.length - 1];
    if (last && family(last[0].kind) === family(event.kind)) last.push(event);
    else runs.push([event]);
  }
  return runs.flatMap((group): EventBundle[] => {
    const single = (event: TrailRecent): EventBundle => ({ event, count: 1, from: event.at, parts: [] });
    if (group.length < 2) return group.map(single);
    const counts = new Map<string, number>();
    for (const event of group) counts.set(event.kind, (counts.get(event.kind) ?? 0) + 1);
    const main = [...counts].sort((a, b) => b[1] - a[1])[0][0];
    const own = group.filter((event) => event.kind === main);
    const prefix = commonPrefix(own.map((event) => event.label || event.kind));
    if (!prefix) return group.map(single);
    const parts: string[] = [];
    for (const event of [...own].reverse()) {
      const rest = (event.label || event.kind).trim().slice(prefix.length).trim();
      if (rest && !parts.includes(rest)) parts.push(rest);
    }
    return [{ event: { ...own[0], label: prefix }, count: group.length, from: group[group.length - 1].at, parts }];
  });
}

/** Relace a změny karty v jedné ose, nejnovější první, nejvýš `settings.limit`; nejnovější relace je v ose vždy a jen ona je rozbalená. */
export function timeline(trail: CardTrail, settings: TrailSettings = TRAIL_SETTINGS): TimelineItem[] {
  const runs: TimelineItem[] = trail.runs.map((run, index) => ({ kind: "run", key: `run:${run.executionId ?? run.taskId ?? index}`,
    at: run.createdAt, run, expanded: false }));
  const events: TimelineItem[] = bundleEvents(trail.recent.filter((event) => !HIDDEN_KINDS.has(event.kind)))
    .map((bundle, index) => ({ kind: "event", key: `event:${index}:${bundle.event.at}`, at: bundle.event.at, ...bundle }));
  const sorted = runs.concat(events).sort((a, b) => moment(b.at) - moment(a.at));
  const limit = Math.max(0, settings.limit);
  const items = sorted.slice(0, limit);
  // Nejnovější relace v ose zůstane vždy, i když ji vytlačí změny karty: bez ní by stopa neřekla, kdo pracoval.
  const lastRun = sorted.find((item) => item.kind === "run");
  if (lastRun && limit > 0 && !items.includes(lastRun)) items[limit - 1] = lastRun;
  const newest = settings.expand === "last-run" ? lastRun : undefined;
  return items.map((item) => (item === newest && item.kind === "run" ? { ...item, expanded: true } : item));
}

/** Osa rozdělená po dnech (Dnes, Včera, datum), aby čas u položky stačil jako HH:MM. */
export function groupByDay(items: TimelineItem[], now: Date = new Date()): TimelineGroup[] {
  const groups: TimelineGroup[] = [];
  for (const item of items) {
    const day = dayKey(item.at);
    const last = groups[groups.length - 1];
    if (last && last.day === day) last.items.push(item);
    else groups.push({ day, label: dayLabel(day, now), items: [item] });
  }
  return groups;
}

export const clock = timeLabel;

/** Kdy relace běžela: „10:42–12:58“ u skončené relace s koncem držení, jinak jen začátek. */
export function runWhen(run: TrailRun): string {
  const start = run.createdAt ? clock(run.createdAt) : "";
  if (!run.until || runState(run.state).tone === "live" || !start) return start;
  const end = clock(run.until);
  return end && end !== start ? `${start}–${end}` : start;
}

/** České tvary počtu: 1 krok, 2 kroky, 5 kroků. */
export function plural(count: number, one: string, few: string, many: string): string {
  return `${count} ${count === 1 ? one : count >= 2 && count <= 4 ? few : many}`;
}

/** Řádka „teď: nástroj · soubor“: nejnovější `tool.use` z běžící relace, jen když kartu někdo právě drží. */
export function nowLine(trail: CardTrail): { text: string; at: string } | null {
  if (!trail.now) return null;
  const since = moment(trail.now.since);
  const used = trail.recent.find((event) => event.kind === "tool.use" && event.label && moment(event.at) >= since);
  return used ? { text: used.label, at: used.at } : null;
}
