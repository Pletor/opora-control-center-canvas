// Stavy srdce se `steps` pro testy a ruční ověření okna „Co srdce dělá“ (než backend kroky posílá všude). Zadání odešlo
// v SENT, plátno se jmenuje FLOW. Tři scénáře: nakreslilo (běží), odpovědělo bez kreslení, chyba.
import type { HeartBatch, HeartStatus, HeartStep } from "@/layout/heart-channel/logic/heart-api";

export const FLOW = "flow-1";
export const SENT = Date.parse("2026-11-04T10:00:05Z");

export const STEPS: HeartStep[] = [
  { t: 800, kind: "thinking", text: "Zadání je jasné: formulář, kontrola, výpočet BMI a uložení. Nejdřív si přečtu skill." },
  { t: 2100, kind: "tool", text: "python opora_heart.py skill proces-na-platne" },
  { t: 3000, kind: "result", text: "skill proces-na-platne: 1 840 znaků" },
  { t: 7400, kind: "tool", text: "python opora_heart.py library nodes" },
  { t: 7900, kind: "result", text: "42 druhů uzlů" },
];

export const message = (flowId = FLOW, at = "2026-11-04T10:00:06Z") => ({ type: "message", text: "Přidej BMI", at, context: { kind: "flow", flowId } });

const idle: HeartStatus = { enabled: true, running: false, pending: 0, batches: [], sleeping: false, sleepingUntil: null, nextAllowedAt: null, error: null, current: null, typicalMs: 60_000 };

export const running = (steps: HeartStep[] = STEPS): HeartStatus => ({ ...idle, running: true, current: { startedAt: "2026-11-04T10:00:06Z", inputs: [message()], steps } });

const batch = (extra: Partial<HeartBatch>): HeartBatch => ({ at: "2026-11-04T10:00:06Z", durationMs: 18_000, inputs: [message()], status: "ok", costUsd: 0.05, summary: null, steps: STEPS, ...extra });

export const answeredOnly = (): HeartStatus => ({ ...idle, batches: [batch({ reply: "Chybí mi, do které tabulky se má BMI ukládat. Napište název tabulky v Asistentovi.", steps: STEPS.slice(0, 3) })] });
export const failed = (): HeartStatus => ({ ...idle, batches: [batch({ status: "rate_limited", error: "Limit předplatného vyčerpán do 12:00.", reply: "" })] });
export const idleStatus = (): HeartStatus => idle;
