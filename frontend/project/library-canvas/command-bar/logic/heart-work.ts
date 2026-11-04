// Co srdce dělá se zadáním z plátna, bez Reactu: která dávka patří našemu zadání, v jaké je fázi (čeká, běží, skončila bez
// kreslení, chyba, zaseklo se), co právě dělá podle posledního kroku a věty pro lištu. Vstupem je stav srdce z backendu.
import type { HeartBatch, HeartInput, HeartStatus, HeartStep } from "@/layout/heart-channel/logic/heart-api";

/** Po této době bez dávky a bez běžícího srdce lišta řekne, že se nic neděje (~3 min). */
export const STALL_MS = 180_000;
/** Dávka skončila, ale draft v plátně může dorazit o chvíli později: dvě otázky na verze, než řekneme „bez kreslení“. */
export const SETTLE_MS = 4000;
/** `at` dávky se zaokrouhluje na vteřinu dolů a hodiny prohlížeče a serveru se smí lišit o chvíli. */
const SLACK_MS = 2000;

export type WorkPhase = "queued" | "running" | "finishing" | "done-no-draw" | "error" | "stalled";

/** Dávka patřící k našemu zadání: běžící, nebo skončená. */
export type Work = { running: boolean; startedAt: string; steps: HeartStep[] | null; reply: string; error: string; failed: boolean; durationMs: number | null };

/** Zpráva z plátna `flowId` poslaná od `sentAt`; čas bere ze vstupu, jinak ze začátku dávky. */
export function isOurs(input: HeartInput, flowId: string, sentAt: number, batchAt: string): boolean {
  if (input.type !== "message") return false;
  const context = input.context as { flowId?: unknown } | undefined;
  if (context?.flowId !== flowId) return false;
  const at = Date.parse(typeof input.at === "string" ? input.at : batchAt);
  return Number.isFinite(at) && at >= sentAt - SLACK_MS;
}

/** Naše dávka ze stavu srdce: běžící má přednost, jinak nejnovější skončená; bez ní `null`. */
export function ownedWork(status: HeartStatus | null, flowId: string, sentAt: number): Work | null {
  if (!status) return null;
  const { current } = status;
  if (current?.inputs?.some((input) => isOurs(input, flowId, sentAt, current.startedAt))) {
    return { running: true, startedAt: current.startedAt, steps: current.steps ?? null, reply: "", error: "", failed: false, durationMs: null };
  }
  const done = (status.batches ?? [])
    .filter((batch) => batch.inputs?.some((input) => isOurs(input, flowId, sentAt, batch.at)))
    .sort((a: HeartBatch, b: HeartBatch) => a.at.localeCompare(b.at)).at(-1);
  if (!done) return null;
  const failed = done.status !== "ok";
  return { running: false, startedAt: done.at, steps: done.steps ?? null, reply: done.reply ?? done.summary ?? "", failed, durationMs: done.durationMs ?? null,
    error: failed ? (done.error || `dávka skončila stavem ${done.status}`) : "" };
}

type PhaseInput = { work: Work | null; status: HeartStatus | null; sentAt: number; now: number; finishedSeenAt: number | null };

/** Fáze čekání na srdce. Draft v plátně (`done-drew`) pozná rodič z verzí, ne odsud. */
export function workPhase({ work, status, sentAt, now, finishedSeenAt }: PhaseInput): WorkPhase {
  if (work?.running) return "running";
  if (work) {
    if (finishedSeenAt === null || now - finishedSeenAt < SETTLE_MS) return "finishing";
    return work.failed ? "error" : "done-no-draw";
  }
  if (status?.running) return "queued";
  return now - sentAt >= STALL_MS ? "stalled" : "queued";
}

/** Fáze, ve kterých se stav srdce ještě ptá; hotové a zaseklé už stačí ukázat. */
export const isActive = (phase: WorkPhase): boolean => phase === "queued" || phase === "running" || phase === "finishing";
/** Fáze, ve kterých se samo otevře okno „Co srdce dělá“. */
export const opensDetail = (phase: WorkPhase): boolean => phase === "done-no-draw" || phase === "error";

/** Co srdce dělá slovy z posledního kroku: příkazy `skill`, `library …` poznáme, ostatní je „pracuje“. */
export function activityOf(steps: readonly HeartStep[] | null): string {
  const last = steps?.at(-1);
  if (!steps || !last) return "pracuje";
  if (last.kind === "thinking") return "přemýšlí";
  if (last.kind === "text") return "píše";
  const tool = [...steps].reverse().find((step) => step.kind === "tool")?.text ?? "";
  if (/\bskill\b/.test(tool)) return "čte skill";
  if (/library\s+nodes/.test(tool)) return "zjišťuje druhy uzlů";
  if (/library\s+get/.test(tool)) return "čte plátno";
  if (/library\s+case/.test(tool)) return "zkouší případ";
  if (/\blibrary\b/.test(tool)) return "kreslí uzly";
  return "pracuje";
}

export const seconds = (ms: number): string => `${Math.max(0, Math.round(ms / 1000))} s`;
/** Čas kroku od začátku dávky: „0:07“, „1:25“. */
export const stepTime = (ms: number): string => { const s = Math.max(0, Math.floor(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

/** Věta v liště: „Srdce čte skill… 12 s · krok 3 · obvykle ~60 s“; ve frontě jen čekání. */
export function barText(phase: WorkPhase, work: Work | null, elapsedMs: number, typicalMs: number | null | undefined): string {
  if (phase === "queued") return `Srdce se probouzí… ${seconds(elapsedMs)}`;
  if (phase === "stalled") return "Srdce se zadáním nezačalo, nic se neděje déle než 3 minuty.";
  if (phase === "done-no-draw") return "Srdce odpovědělo, ale nic nenakreslilo.";
  if (phase === "error") return "Srdce skončilo chybou.";
  const parts = [`Srdce ${phase === "finishing" ? "dokončuje" : activityOf(work?.steps ?? null)}… ${seconds(elapsedMs)}`];
  if (work?.steps?.length) parts.push(`krok ${work.steps.length}`);
  if (typicalMs) parts.push(`obvykle ~${seconds(typicalMs)}`);
  return parts.join(" · ");
}
