// Čisté odvození líce živé karty: slova stavů, pruhy pravd, vazby, řady pro sparkline, dráhy aktérů a převod
// události toku na řádek deníku. Bez Reactu, testy v live-card-view.test.ts.
import type { OporaEvent } from "@/editor/live-strip/logic/events-client";
import { eventText } from "@/editor/live-strip/logic/live-model";
import type { FutureWork, ItemStatus, LiveFlow, MirrorItem, MirrorTruth, LiveRun, PendingTruth, RecentItem, Truth } from "./live-card-types";

export type Tone = "vision" | "mirror" | "real" | "future" | "work" | "risk" | "heart" | "plain";

const STATES: Record<string, [string, Tone]> = {
  seed: ["Semínko", "vision"], bud: ["Vývoj", "work"], leaf: ["Doloženo", "real"],
  dry: ["Slepá cesta", "risk"], prop: ["Návrh srdce", "future"], goal: ["Cíl", "vision"],
};
export const stateView = (state: string) => { const [label, tone] = STATES[state] ?? [state || "—", "plain" as Tone]; return { label, tone }; };

export const MARK: Record<ItemStatus, string> = { ok: "✓", miss: "○", bad: "✕", wait: "◌" };
export const markOfStatus = (status: string) => MARK[status as ItemStatus] ?? "·";

export const isPending = (truth: Truth | MirrorTruth | PendingTruth | null): truth is PendingTruth =>
  !!truth && (truth as PendingTruth).available === false;

/** Pruh pravdy: kolik položek je ✓ z celku; prázdná pravda pruh nemá. */
export function truthBar(truth: Truth): { done: number; total: number; pct: number } | null {
  const total = truth.items.length;
  if (!total) return null;
  const done = truth.items.filter(item => item.status === "ok").length;
  return { done, total, pct: Math.round(done / total * 100) };
}

/** Pruh shody zrcadla: nalezené z očekávaných (shoda + chybí); „navíc“ shodu nesnižuje, svítí zvlášť červeně. */
export function mirrorBar(mirror: MirrorTruth): { done: number; total: number; pct: number } | null {
  const { matched, missing } = mirror.counts;
  const total = matched + missing;
  return total ? { done: matched, total, pct: Math.round(matched / total * 100) } : null;
}
/** Místo v kódu jako `soubor:řádek`; bez řádku jen soubor. */
export const mirrorPlace = (item: MirrorItem) => item.path + (typeof item.line === "number" ? `:${item.line}` : "");

const RELATIONS: [RegExp, string, Tone][] = [
  [/^(vyžaduje|requires?)$/i, "vyžaduje", "vision"], [/^(používá|uses?)$/i, "používá", "work"],
  [/^(dokládá|proves?)$/i, "dokládá", "real"], [/^(sdílí kód|shares?[_ -]?code)$/i, "sdílí kód", "mirror"],
];
/** Teleport: popisek vazby, barva, šipka podle směru; sdílený kód je čárkovaný, protože vznikl z commitů. */
export function relationView(relation: string | null, dir: "in" | "out") {
  const hit = relation ? RELATIONS.find(([pattern]) => pattern.test(relation.trim())) : undefined;
  const label = hit?.[1] ?? relation ?? "vazba";
  const tone: Tone = hit?.[2] ?? "plain";
  return { label, tone, arrow: hit?.[1] === "sdílí kód" ? "⇄" : dir === "out" ? "→" : "←", dashed: hit?.[1] === "sdílí kód" };
}

/** Body polyline pro sparkline (`w`×`h`); bez aspoň dvou čísel se křivka nekreslí. */
export function sparkPoints(values: (number | null)[], w = 300, h = 44): string | null {
  const numbers = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (numbers.length < 2) return null;
  const max = Math.max(...numbers) || 1, step = w / (numbers.length - 1);
  return numbers.map((value, index) => `${Math.round(index * step * 10) / 10},${Math.round((h - 4 - value / max * (h - 10)) * 10) / 10}`).join(" ");
}

const byTime = (runs: LiveRun[]) => [...runs].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
export const testSeries = (runs: LiveRun[]) => byTime(runs).map(run => run.tests && run.tests.total ? run.tests.passed / run.tests.total : null);
export const costSeries = (runs: LiveRun[]) => byTime(runs).map(run => run.costUsd);
export const latestRun = (runs: LiveRun[]): LiveRun | null => byTime(runs).at(-1) ?? null;

/** Zdroj na líci: jen cesta bez query; plná adresa patří do `title`. */
export const sourcePath = (url: string) => url.split("?")[0];
/** Zdroj na rubu: cesta a jména parametrů bez hodnot (`/api/x?project&workspace&nodeId`). */
export function sourceShape(url: string) {
  const at = url.indexOf("?");
  if (at < 0) return url;
  const names = [...new URLSearchParams(url.slice(at + 1)).keys()];
  return names.length ? `${url.slice(0, at)}?${names.join("&")}` : url.slice(0, at);
}

export const usd = (value: number | null | undefined) => typeof value === "number" ? value.toFixed(2).replace(".", ",") : "—";

/** Čas do deníku: HH:MM pro dnešek, jinak D. M.; nečitelný text se vrátí zkrácený. */
export function clock(at: string, now = new Date()): string {
  const date = new Date(at);
  if (Number.isNaN(date.getTime())) return at.slice(0, 5);
  const pad = (n: number) => String(n).padStart(2, "0");
  return date.toDateString() === now.toDateString() ? `${pad(date.getHours())}:${pad(date.getMinutes())}` : `${date.getDate()}. ${date.getMonth() + 1}.`;
}

export const RECENT_MAX = 30;
export const STREAM_SOURCE = "/api/oporahub/events/stream";
type ProcessFields = { title?: string | null; tool?: { target?: string } | null };
/** Událost toku jako řádek deníku karty (stejný tvar jako `recent[]` z API); druh bez vlastního textu (Kancelář,
 *  zásah srdce, signál hlídače) vezme titulek z toku a u nástroje i cíl, jako `card_trail.recent`. */
export function eventToRecent(event: OporaEvent): RecentItem {
  const { title, tool } = event as OporaEvent & ProcessFields;
  const known = eventText(event);
  const text = known === event.kind && title ? (tool?.target ? `${title} · ${tool.target}` : title) : known;
  return { at: event.at, actor: event.actor.name || event.actor.kind, kind: event.kind, text, source: STREAM_SOURCE };
}
/** Nové události nahoru, deník drží nejvýš 30 řádků. */
export const prependRecent = (recent: RecentItem[], fresh: RecentItem[]) => [...fresh, ...recent].slice(0, RECENT_MAX);
/** Deník z API + živé řádky: událost, kterou už API vrátilo (po Obnovit, nebo v okně před prvním snímkem), se neopakuje. */
export function mergeRecent(api: RecentItem[], live: RecentItem[]) {
  const known = new Set(api.map(item => `${item.at}|${item.kind}`));
  return prependRecent(api, live.filter(item => !known.has(`${item.at}|${item.kind}`)));
}

const ACTORS: [RegExp, Tone, string][] = [
  [/heart|srdce/i, "heart", "Srdce"], [/guard|hlídač|watch|review/i, "risk", "Hlídač"],
  [/trigger|hook|system|linie/i, "mirror", "Trigger"], [/human|člověk|user/i, "vision", "Člověk"],
];
// Druh události rozhoduje dřív než jméno aktéra: zásah srdce, práce dělníka v Kanceláři (F2).
const KIND_LANES: [RegExp, Tone, string][] = [
  [/^worker\.message$/, "heart", "Srdce"], [/^(tool\.use|turn\.|worker\.|needs\.input)/, "work", "Dělník"],
];
/** Dráha aktéra podle druhu, pak jména: srdce, hlídač (`card.signal` od hlídače), trigger, člověk, jinak dělník. */
export function actorView(actor: string, kind = ""): { tone: Tone; lane: string } {
  const hit = KIND_LANES.find(([pattern]) => pattern.test(kind)) ?? ACTORS.find(([pattern]) => pattern.test(actor));
  return hit ? { tone: hit[1], lane: hit[2] } : { tone: "work", lane: "Dělník" };
}

/** Dráhy aktérů nad deníkem: značka = událost, x = poloha v čase mezi nejstarší a nejnovější. */
export function runLanes(recent: RecentItem[]) {
  const times = recent.map(item => Date.parse(item.at)).filter(Number.isFinite);
  if (!times.length) return [];
  const from = Math.min(...times), span = Math.max(...times) - from || 1;
  const lanes = new Map<string, { lane: string; tone: Tone; ticks: number[] }>();
  for (const item of recent) {
    const time = Date.parse(item.at);
    if (!Number.isFinite(time)) continue;
    const { lane, tone } = actorView(item.actor, item.kind);
    const row = lanes.get(lane) ?? { lane, tone, ticks: [] };
    row.ticks.push(Math.round((time - from) / span * 970) / 10);
    lanes.set(lane, row);
  }
  return [...lanes.values()];
}

const label = (value: unknown): string => {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return String(record.name ?? record.label ?? record.title ?? record.id ?? "");
  }
  return value == null ? "" : String(value);
};
const labels = (value: unknown) => (Array.isArray(value) ? value : value == null ? [] : [value]).map(label).filter(Boolean);
/** Tok dat do tří sloupců vstupy → kroky → výstupy (+ kam data tečou); prázdný tok se nekreslí. */
export function flowColumns(flow: LiveFlow) {
  const columns = [labels(flow.inputs), labels(flow.steps), [...labels(flow.outputs), ...labels(flow.dataTo)]];
  return { columns, conditions: labels(flow.conditions), empty: columns.every(column => !column.length) };
}

const VERDICTS: Record<string, [string, ItemStatus]> = {
  clean: ["čisté sloučení", "ok"], warning: ["dopad na sousedy", "wait"], blocked: ["konflikt", "bad"],
};
/** Verdikt budoucnosti slovem a stavem položky; neznámý verdikt se nevydává za čistý. */
export const futureVerdict = (verdict: string) => { const [label, status] = VERDICTS[verdict] ?? [verdict || "—", "miss" as ItemStatus]; return { label, status }; };

/** Řádky jedné otevřené práce: konflikty (rozpor), dopady na karty a překryvy s jinými úkoly (varování). */
export function futureLines(work: FutureWork): { status: ItemStatus; text: string; title: string }[] {
  const files = (paths: string[]) => paths.length ? ` · ${paths.slice(0, 3).join(", ")}${paths.length > 3 ? ` +${paths.length - 3}` : ""}` : "";
  return [
    ...work.conflicts.map(path => ({ status: "bad" as ItemStatus, text: `konflikt ${path}`, title: path })),
    ...work.impacts.map(item => ({ status: "wait" as ItemStatus, text: `${item.name} (${item.via === "shares_code" ? "sdílí kód" : item.via})${files(item.paths)}`, title: item.paths.join("\n") })),
    ...work.overlaps.map(item => ({ status: "wait" as ItemStatus, text: `${item.mark ?? item.branch} mění totéž${files(item.paths)}`, title: item.paths.join("\n") })),
  ];
}

const MIRROR_ORDER: Record<string, number> = { bad: 0, miss: 1, ok: 2 };

/** Zrcadlo velké větve má stovky položek: nahoře ujetí a chybějící, pak shoda; víc než `limit` až na rozbalení. */
export function mirrorShown(items: MirrorItem[], limit: number, all: boolean): { shown: MirrorItem[]; rest: number } {
  const sorted = [...items].sort((a, b) => (MIRROR_ORDER[a.status] ?? 3) - (MIRROR_ORDER[b.status] ?? 3));
  return all ? { shown: sorted, rest: 0 } : { shown: sorted.slice(0, limit), rest: Math.max(0, sorted.length - limit) };
}
