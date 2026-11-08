// Panel „Co dělá Srdce“ v HUD a okně Pletora bez Reactu: ze stavu srdce (`GET /api/brain/heart/status`,
// docs/brain-heart-channel.md §1 bod 3) a otevřené otázky Pletora jedna věta pro člověka: čekat, nebo mluvit.
import type { HeartBatch, HeartStatus, HeartStep } from "@/layout/heart-channel/logic/heart-api";
import { wakeReason } from "@/layout/heart-channel/logic/heart-live";
import { inputs } from "@/layout/heart-channel/logic/heart-status";

export type HeartPanelKind = "answer" | "working" | "queued" | "error" | "sleeping" | "unavailable";
export type HeartPanelView = { kind: HeartPanelKind; title: string; detail: string; hint: string; steps: HeartStep[] };

/** Kolik posledních kroků běžící dávky panel ukáže (nejnovější dole). */
export const STEPS_SHOWN = 6;
/** Rytmus pollingu: během práce srdce častěji, jinak volněji (ms). */
export const WORK_POLL_MS = 3000;
export const IDLE_POLL_MS = 5000;

const pad = (n: number) => String(n).padStart(2, "0");

/** Uplynulý čas „2:14“, nad hodinu „1:02:14“. */
export function elapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`;
}

/** Typická délka dávky „~3 min“, krátká „~45 s“. */
export function typical(ms: number): string {
  return ms < 90_000 ? `~${Math.max(1, Math.round(ms / 1000))} s` : `~${Math.round(ms / 60_000)} min`;
}

/** Jeden řádek: bílé znaky slité, dlouhý text zkrácený výpustkou. */
export function oneLine(text: string, max: number): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max - 1).trimEnd()}…` : flat;
}

const lastBatch = (batches: HeartBatch[] | undefined) =>
  [...(batches ?? [])].sort((a, b) => a.at.localeCompare(b.at)).at(-1);

const view = (kind: HeartPanelKind, title: string, detail = "", hint = "", steps: HeartStep[] = []): HeartPanelView =>
  ({ kind, title, detail, hint, steps });

/**
 * Přednost: odpověď připravená > pracuje > fronta > chyba > spí. Odpověď nese otázka Pletora, ne stav srdce,
 * proto přebije i nedostupný stav (`status === null`, dotaz selhal).
 */
export function heartPanel({ status, answered, now }: { status: HeartStatus | null; answered: boolean; now: number }): HeartPanelView {
  if (answered) return view("answer", "Srdce má odpověď na tvou otázku · mluv s Pletorem");
  if (!status) return view("unavailable", "Stav srdce nedostupný");
  if (status.running) {
    const current = status.current;
    const started = current ? Date.parse(current.startedAt) : NaN;
    const since = Number.isNaN(started) ? "" : ` · ${elapsed(now - started)}`;
    const usual = status.typicalMs ? ` (obvykle ${typical(status.typicalMs)})` : "";
    const first = current?.inputs?.[0]?.text;
    const quote = typeof first === "string" && first.trim() ? ` · „${oneLine(first, 60)}“` : "";
    const detail = current ? `probudilo: ${wakeReason(current.inputs ?? [])}${quote}` : "";
    const steps = (current?.steps ?? []).slice(-STEPS_SHOWN).map((step) => ({ ...step, text: oneLine(step.text, 160) }));
    return view("working", `Srdce pracuje${since}${usual}`, detail, "Můžeš mluvit s Pletorem, Srdce pracuje na pozadí.", steps);
  }
  // Limit předplatného: vstupy čekají, ale „za chvíli začne“ by lhalo
  const wait = status.sleeping && status.sleepingUntil ? ` až po ${new Date(status.sleepingUntil).toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" })}` : "";
  if (status.pending > 0) return view("queued", `Srdce má ve frontě ${inputs(status.pending)}, ${status.sleeping ? `čeká na limit předplatného${wait}` : "za chvíli začne"}.`);
  if (status.error) return view("error", `Chyba srdce: ${status.error}`);
  const summary = lastBatch(status.batches)?.summary;
  return view("sleeping", "Srdce spí", summary ? `naposledy: ${oneLine(summary, 120)}` : "");
}

/** Další krok pollingu podle stavu srdce: běžící dávka se sleduje každé 3 s, jinak každých 5 s. */
export const pollMs = (status: HeartStatus | null | undefined) => (status?.running ? WORK_POLL_MS : IDLE_POLL_MS);

/** Krátký štítek kroku podle druhu (myšlenka, text, příkaz, výsledek). */
export const STEP_TAG: Record<HeartStep["kind"], string> = { thinking: "myslí", text: "píše", tool: "příkaz", result: "výsledek" };
