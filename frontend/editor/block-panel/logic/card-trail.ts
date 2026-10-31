// Stopa práce karty z `GET /api/oporahub/card-trail` (docs/stopa-prace-karty.md): typy odpovědi a přísné, ale
// tolerantní čtení. Celek bez `nodeId` je chyba; jednotlivá položka v jiném tvaru se vynechá, ne zobrazí napůl.
// Čistá data bez Reactu; panel bloku z nich jen kreslí.
import { isObject, scopeQuery } from "@/hub/oporahub-mirror/logic/hub-read";
import { parseAfterMerge, type AfterMerge } from "@/hub/oporahub-card-drawer/logic/card-dod";

/** Původ textu: odvodil kód, napsal dělník, doplnilo srdce, napsal člověk. */
export type TrailSource = "det" | "agent" | "heart" | "human";
export type TrailCheck = { name: string; status: "green" | "red" | "unknown" };
export type TrailStep = {
  stepId: string; title: string; status: string; checks: TrailCheck[]; commits: string[]; notes: string;
  source: TrailSource; files: string[] | null; allowed: string[];
};
export type TrailRun = {
  executionId: string | null; taskId: string | null; owner: string; createdAt: string; until: string | null;
  state: string; summary: string; source: TrailSource; attempts: number; reported: boolean; steps: TrailStep[];
};
export type TrailNow = { owner: string; since: string; until: string | null; stepId: string | null };
export type TrailRecent = { at: string; who: string; label: string; kind: string; source: TrailSource };
export type TrailPort = {
  edgeId: string; targetId: string; targetName: string | null; summary: string; handoff: string; by: string;
  updatedAt: string | null; source: TrailSource;
};
export type TrailJudgment = {
  code: string; stepId: string | null; executionId: string | null; reason: string; outside: string[]; source: TrailSource;
};
export type TrailPr = { number: number | null; state: "open" | "merged" | "closed" };
export type CardTrail = {
  nodeId: string; now: TrailNow | null; runs: TrailRun[]; pr: TrailPr | null; missing: string[];
  recent: TrailRecent[]; ports: TrailPort[]; judgment: TrailJudgment[]; filesKnown: boolean;
  /** Co uznalo sloučení, protože přibylo do zadání až po něm (mimo standardní proces); null u běžné karty. */
  afterMerge: AfterMerge | null;
};

const SOURCES: TrailSource[] = ["det", "agent", "heart", "human"];
const text = (value: unknown): string => (typeof value === "string" ? value : "");
const textOrNull = (value: unknown): string | null => (typeof value === "string" && value ? value : null);
const texts = (value: unknown): string[] => (Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []);
const source = (value: unknown): TrailSource => (SOURCES.includes(value as TrailSource) ? (value as TrailSource) : "det");
const list = <T>(value: unknown, read: (raw: Record<string, unknown>) => T | null): T[] =>
  Array.isArray(value) ? value.flatMap((item) => { const out = isObject(item) ? read(item) : null; return out ? [out] : []; }) : [];

function check(raw: Record<string, unknown>): TrailCheck | null {
  if (!text(raw.name)) return null;
  const status = raw.status === "green" || raw.status === "red" ? raw.status : "unknown";
  return { name: text(raw.name), status };
}

function step(raw: Record<string, unknown>): TrailStep | null {
  if (!text(raw.stepId)) return null;
  return { stepId: text(raw.stepId), title: text(raw.title), status: text(raw.status) || "pending", checks: list(raw.checks, check),
    commits: texts(raw.commits), notes: text(raw.notes), source: source(raw.source),
    files: Array.isArray(raw.files) ? texts(raw.files) : null, allowed: texts(raw.allowed) };
}

function run(raw: Record<string, unknown>): TrailRun | null {
  if (!text(raw.createdAt) && !text(raw.state)) return null;
  return { executionId: textOrNull(raw.executionId), taskId: textOrNull(raw.taskId), owner: text(raw.owner),
    createdAt: text(raw.createdAt), until: textOrNull(raw.until), state: text(raw.state), summary: text(raw.summary),
    source: source(raw.source), attempts: Number.isSafeInteger(raw.attempts) ? Number(raw.attempts) : 0,
    reported: raw.reported === true, steps: list(raw.steps, step) };
}

function recent(raw: Record<string, unknown>): TrailRecent | null {
  if (!text(raw.at)) return null;
  return { at: text(raw.at), who: text(raw.who), label: text(raw.label), kind: text(raw.kind), source: source(raw.source) };
}

function port(raw: Record<string, unknown>): TrailPort | null {
  if (!text(raw.edgeId)) return null;
  return { edgeId: text(raw.edgeId), targetId: text(raw.targetId), targetName: textOrNull(raw.targetName),
    summary: text(raw.summary), handoff: text(raw.handoff), by: text(raw.by), updatedAt: textOrNull(raw.updatedAt), source: source(raw.source) };
}

function judgment(raw: Record<string, unknown>): TrailJudgment | null {
  if (!text(raw.code)) return null;
  return { code: text(raw.code), stepId: textOrNull(raw.stepId), executionId: textOrNull(raw.executionId),
    reason: text(raw.reason), outside: texts(raw.outside), source: source(raw.source) };
}

function now(raw: unknown): TrailNow | null {
  if (!isObject(raw) || !text(raw.since)) return null;
  return { owner: text(raw.owner), since: text(raw.since), until: textOrNull(raw.until), stepId: textOrNull(raw.stepId) };
}

function pr(raw: unknown): TrailPr | null {
  if (!isObject(raw) || !["open", "merged", "closed"].includes(raw.state as string)) return null;
  return { number: Number.isSafeInteger(raw.number) ? Number(raw.number) : null, state: raw.state as TrailPr["state"] };
}

export function parseCardTrail(raw: unknown): CardTrail {
  if (!isObject(raw) || !text(raw.nodeId)) throw new Error("Stopa práce karty má neplatný tvar.");
  return { nodeId: text(raw.nodeId), now: now(raw.now), runs: list(raw.runs, run), pr: pr(raw.pr), missing: texts(raw.missing),
    recent: list(raw.recent, recent), ports: list(raw.ports, port), judgment: list(raw.judgment, judgment), filesKnown: raw.filesKnown === true,
    afterMerge: parseAfterMerge(raw.afterMerge) };
}

export function cardTrailUrl(project: string, workspace: string, node: string): string {
  return `/api/oporahub/card-trail?${scopeQuery({ project, workspace, node })}`;
}
