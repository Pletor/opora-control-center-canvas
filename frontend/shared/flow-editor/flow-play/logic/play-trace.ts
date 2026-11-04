// Přehrávání trasy simulace (kontrakt `docs/navrhy/2026-11-04-platno-procesu.md` §4) jako čisté funkce: tvar odpovědi
// `POST /api/flow/simulate`, výběr dalšího kroku, hrana, po které bod letí, a krátký popisek dat u bodu.
// Výpočet dělá server; tady se trasa jen prochází.
import type { FlowGraph } from "../../logic/flow-types";

export type TraceStep = {
  step: number; nodeId: string; edgeId?: string | null; layer: string; type: string; in: unknown; rule?: string | null; out: unknown;
  branch?: string | null; note: string; error?: string | null;
};
export type SimulateExpect = { ok: boolean; diffs: string[] };
export type SimulateResponse = { ok: boolean; result: unknown; trace: TraceStep[]; expect: SimulateExpect | null };

export const SPEEDS = [1, 2, 4] as const;
export type Speed = typeof SPEEDS[number];
/** Jak dlouho trvá jeden krok při rychlosti 1× (let bodu po hraně); vyšší rychlost dobu dělí. */
export const STEP_MS = 1100;
export const stepMs = (speed: Speed) => STEP_MS / speed;

/** Index kroku po posunu o `direction`; `null` = trasa skončila (za posledním krokem) nebo začíná (před prvním). */
export function nextIndex(index: number, length: number, direction: 1 | -1): number | null {
  const next = index + direction;
  return next < 0 || next >= length ? null : next;
}

/** Hrana, po které do kroku `index` přiletí bod: `edgeId` kroku, jinak hrana z předchozího uzlu trasy, jinak nic. */
export function stepEdge(graph: FlowGraph, trace: readonly TraceStep[], index: number): string | null {
  const step = trace[index], previous = trace[index - 1];
  if (!step) return null;
  if (step.edgeId) return step.edgeId;
  if (!previous) return null;
  return graph.edges.find((edge) => edge.source_node === previous.nodeId && edge.target_node === step.nodeId)?.id ?? null;
}

/** Zkrácený JSON dat pro popisek u bodu; dlouhý obsah se utne třemi tečkami. */
export function dataLabel(value: unknown, max = 32): string {
  if (value === undefined) return "";
  const text = typeof value === "string" ? value : JSON.stringify(value) ?? "";
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export const pretty = (value: unknown): string => value === undefined ? "" : JSON.stringify(value, null, 2);

/** Věta o konci případu pro souhrn: shoda s `expect`, neshoda, nebo že očekávání chybí. */
export function verdict(response: SimulateResponse): { tone: "ok" | "fail" | "idle"; text: string } {
  if (!response.expect) return { tone: "idle", text: "Případ nemá očekávání (expect), nelze ho porovnat." };
  return response.expect.ok ? { tone: "ok", text: "Shoda s očekáváním." } : { tone: "fail", text: "Neshoda s očekáváním." };
}

/** Trasa jako řádek „a → b → c“ pro souhrn. */
export const routeText = (trace: readonly TraceStep[]): string => trace.map((step) => step.nodeId).join(" → ");

/** Věta o chybě volání simulace: 422 s důvodem serveru, výpadek jako stav spojení. */
export function simulateError(error: unknown): string {
  const body = (error as { body?: { detail?: unknown; error?: unknown } } | null)?.body;
  const detail = typeof body?.detail === "string" ? body.detail : Array.isArray(body?.detail) ? body.detail.map((item) => (item as { msg?: string })?.msg ?? "").filter(Boolean).join(" · ") : "";
  const status = (error as { status?: number } | null)?.status;
  if (status === 422) return `Simulace případ odmítla: ${detail || (error as Error).message}`;
  return `Simulaci se nepodařilo spustit: ${error instanceof Error ? error.message : String(error)}`;
}
