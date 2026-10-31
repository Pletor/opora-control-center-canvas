// Srdce právě teď (docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md §A) bez Reactu: co dávku probudilo,
// řádek „Pracuje od …“, dotaz na zápisy srdce v záznamu činnosti a jejich věty. Popisky akcí a jména karet
// bere ze záznamu činnosti (`activity-log.ts`), aby obě místa mluvila stejně.
import {
  actionLabel, isFailed, nodeRefs, summaryDetail, timeLabel, type ActivityEntry,
} from "@/editor/canvas/activity-log/logic/activity-log";
import type { HeartBatch, HeartCurrent, HeartInput } from "./heart-api";
import { clock } from "./heart-status";

/** Jméno, pod kterým se srdce hlásí v `X-Opora-Actor` (opora_heart.py `call`). */
export const HEART_AGENT = "heart";

const TICKETS: Record<string, string> = { ask: "otázka pracovníka", change: "žádost o změnu pracovníka" };

/** Jeden vstup dávky lidsky: zpráva člověka, odpověď na otázku, sloučení PR #N, lístek pracovníka… */
export function inputLabel(input: HeartInput): string {
  switch (input.type) {
    case "message":
      return typeof input.text === "string" && input.text.startsWith("ODPOVĚĎ ČLOVĚKA") ? "odpověď na otázku" : "zpráva člověka";
    case "ticket":
      return TICKETS[String(input.kind)] ?? "lístek pracovníka";
    case "merged":
      return input.pr ? `sloučení PR #${input.pr}` : "lokální sloučení";
    case "commits": return "nové commity";
    case "taskFailed": return "selhaný úkol";
    case "milestoneDone": return "splněný milník";
    case "cardTrigger": return "spouštěč karty";
    case "brief": return "výslech požadavku";
    case "humanChange": return "změna plánu člověkem";
    default: return "událost brány";
  }
}

/** Co dávku probudilo: první vstup a počet dalších („zpráva člověka + 2 další“). */
export function wakeReason(inputs: HeartInput[]): string {
  if (inputs.length === 0) return "dohánění vstupů";
  const more = inputs.length - 1;
  return inputLabel(inputs[0]) + (more > 0 ? ` + ${more} další` : "");
}

/** Řádek běžící dávky: „Pracuje od 11:51 · probudilo: sloučení PR #42“. */
export function liveLine(current: HeartCurrent): string {
  const since = clock(current.startedAt);
  return `Pracuje${since ? ` od ${since}` : ""} · probudilo: ${wakeReason(current.inputs ?? [])}`;
}

export type StepRange = { since: string; until?: string };

/** Rozsah kroků skončené dávky: deník píše `at` = začátek, trvání je `durationMs` (+1 s na zaokrouhlení `at`). */
export function batchRange(batch: Pick<HeartBatch, "at" | "durationMs">): StepRange | null {
  const start = Date.parse(batch.at);
  if (Number.isNaN(start) || typeof batch.durationMs !== "number") return null;
  return { since: batch.at, until: new Date(start + batch.durationMs + 1000).toISOString() };
}

/** Dotaz na zápisy srdce v projektu za rozsah (záznam činnosti nese jen zápisy, čtení ne). */
export function heartStepsQuery(project: string, range: StepRange, limit = 100): string {
  const params = new URLSearchParams({ project, actor: "agent", agent: HEART_AGENT, since: range.since, limit: String(limit) });
  if (range.until) params.set("until", range.until);
  return "/api/activity-log?" + params.toString();
}

/** Upřesnění podle konce cesty: zrušení úkolu, přijetí návrhu, odpověď na lístek. */
const ENDINGS: [string, string][] = [["/cancel", "Zrušení úkolu"], ["/accept", "Přijetí návrhu"], ["/answer", "Odpověď na lístek"]];

/** Věta kroku: popisek akce (záznam činnosti), upřesnění z konce cesty a druh operace ze `summary`. */
export function stepText(entry: Pick<ActivityEntry, "path" | "summary">): string {
  const path = entry.path.split("?")[0];
  const ending = ENDINGS.find(([suffix]) => path.endsWith(suffix));
  const label = ending ? ending[1] : actionLabel(path);
  const detail = summaryDetail(entry.summary);
  return detail ? `${label} · ${detail}` : label;
}

export type StepRow = { key: number; time: string; text: string; cards: string[]; failed: boolean; status: number };

/** Zápisy srdce → řádky kroků, nejnovější nahoře; čtení (GET) se nikdy neukazuje. */
export function stepRows(entries: ActivityEntry[], nodes: { id: string; name: string }[]): StepRow[] {
  return entries
    .filter((entry) => entry.method !== "GET" && entry.method !== "HEAD")
    .sort((a, b) => b.id - a.id)
    .map((entry) => ({
      key: entry.id,
      time: timeLabel(entry.at),
      text: stepText(entry),
      cards: nodeRefs(entry.nodeIds ?? [], nodes).map((ref) => ref.name),
      failed: isFailed(entry.status),
      status: entry.status,
    }));
}
