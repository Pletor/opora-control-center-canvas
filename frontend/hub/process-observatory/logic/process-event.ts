// Událost živého procesu (`opora.process-event/1`, docs/zivy-proces.md §2) tak, jak ji čte pohled
// „Živý proces“. Sdílený klient toku (`editor/live-strip/logic/events-client.ts`) dává původní pole outboxu;
// pole živého procesu (`source`, `phase`, `state`, `title`, `refs`, `tool`, `eventId`) jsou v JSON navíc
// a tady se jednou přečtou do plochého tvaru. Nic se nedomýšlí: chybějící pole zůstane prázdné.
import type { OporaEvent } from "@/editor/live-strip/logic/events-client";

export const PHASES = [
  ["intake", "Zadání"], ["plan", "Plán"], ["work", "Práce"], ["checks", "Kontroly"],
  ["review", "Revize"], ["merge", "Sloučení"], ["memory", "Paměť"],
] as const;
export type PhaseId = typeof PHASES[number][0];
export const PHASE_IDS = PHASES.map(([id]) => id) as PhaseId[];
export const phaseIndex = (phase: string | null | undefined) => PHASE_IDS.indexOf(phase as PhaseId);
export const phaseName = (index: number) => PHASES[index]?.[1] ?? "—";

export const STATES = ["start", "progress", "ok", "fail", "wait", "blocked", "info"] as const;
export type ProcessState = typeof STATES[number];
export type ProcessSource = "office" | "opora" | "github";
export const SOURCE_NAME: Record<ProcessSource, string> = { office: "Kancelář", opora: "Opora", github: "GitHub" };

type Refs = { cardId?: string; executionId?: string; workerId?: string; floor?: string; branch?: string; pr?: number; sha?: string; url?: string };
type Tool = { name: string; action?: string; target?: string };
/** Drátový tvar: původní pole outboxu + pole živého procesu (starší server je nemá). */
export type WireProcessEvent = OporaEvent & {
  source?: string | null; phase?: string | null; state?: string | null; title?: string | null; detail?: string | null;
  refs?: Refs | null; tool?: Tool | null; eventId?: string | null; schema?: string | null;
};

export type FlowEvent = {
  key: string; id: number; at: string; ms: number; source: ProcessSource; kind: string;
  phase: number; state: ProcessState; title: string; detail: string;
  cardId: string | null; workerId: string; workerName: string; executionId: string | null;
  branch: string; pr: number | null; sha: string; url: string; floor: string; tool: Tool | null;
};

const str = (value: unknown) => typeof value === "string" ? value : "";
const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};

/** Plochá událost pro mapu, proud i inspektor. Čas u kanceláře je čas zdroje (`data.sourceAt`). */
export function toFlowEvent(raw: OporaEvent): FlowEvent {
  const wire = raw as WireProcessEvent;
  const refs = record(wire.refs) as Refs;
  const data = record(wire.data);
  const worker = record(data.actor);
  const source: ProcessSource = wire.source === "office" || wire.source === "github" ? wire.source : "opora";
  const at = str(data.sourceAt) || wire.at;
  // U kanceláře a GitHubu je `actor` jen identita producenta (hlavička); pracovník je v `data.actor` / `refs.workerId`.
  const agentName = source === "opora" && wire.actor?.kind === "agent" ? wire.actor.name : "";
  const state = (STATES as readonly string[]).includes(wire.state ?? "") ? wire.state as ProcessState : "info";
  return {
    key: wire.eventId || `opora:${wire.id}`, id: wire.id, at, ms: Date.parse(at) || 0, source, kind: wire.kind,
    phase: phaseIndex(wire.phase), state, title: wire.title || wire.kind, detail: wire.detail ?? "",
    cardId: wire.nodeId ?? refs.cardId ?? null,
    workerId: str(refs.workerId) || str(worker.id) || agentName,
    workerName: str(worker.name) || agentName || str(refs.workerId),
    executionId: wire.executionId ?? refs.executionId ?? null,
    branch: str(refs.branch), pr: wire.prNumber ?? (typeof refs.pr === "number" ? refs.pr : null),
    sha: str(refs.sha), url: str(refs.url), floor: str(refs.floor), tool: wire.tool ?? null,
  };
}

/** Sloučí nové události do seznamu bez dvojic (klíč `eventId`), seřazené podle kurzoru, nejvýš `keep`. */
export function mergeEvents(list: FlowEvent[], incoming: FlowEvent[], keep = 300): FlowEvent[] {
  const seen = new Set(list.map((event) => event.key));
  const fresh = incoming.filter((event) => !seen.has(event.key) && seen.add(event.key));
  if (!fresh.length) return list;
  return [...list, ...fresh].sort((a, b) => a.id - b.id).slice(-keep);
}

/** „Vývojář 1“ → „V1“, „Ada“ → „AD“; bez jména pomlčka. */
export function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return "—";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export const clock = (at: string) => { const ms = Date.parse(at); return Number.isFinite(ms) ? new Date(ms).toLocaleTimeString("cs-CZ") : "—"; };
/** „před 12 s“ / „před 3 min“ / „před 2 h“; neznámý čas pomlčka. */
export function ago(ms: number, now: number) {
  if (!ms) return "—";
  const seconds = Math.max(0, Math.round((now - ms) / 1000));
  if (seconds < 60) return `před ${seconds} s`;
  if (seconds < 3600) return `před ${Math.round(seconds / 60)} min`;
  return `před ${Math.round(seconds / 3600)} h`;
}
