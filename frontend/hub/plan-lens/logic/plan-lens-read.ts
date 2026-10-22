import { ACCESS_REQUIRED_EVENT } from "@/app/access-gate/logic/access-gate";
import { isCount, isObject, scopeQuery } from "@/hub/oporahub-mirror/logic/hub-read";

// Čtení `GET /api/oporahub/plan-lens?project&workspace[&area]`: Lens plánu celého projektu (oblasti a
// předávky) nebo jedné oblasti (karty, vazby z plánu a vazby v kódu z Graphify). Spec je nedůvěryhodný:
// tady se ověří jen obálka, graf ověří schéma PR Lens až v líně načteném plátně. 304 drží data, 404
// znamená starší server bez endpointu, ne chybu.
export type PlanStats = { areas: number; cards: number; withCode: number; planned: number; standalone: number; unassigned: number };
export type PlanLens = {
  area: string | null; digest: string; spec: Record<string, unknown>; stats: PlanStats;
  graphify: { available: boolean; sourceRevision: string | null };
};
export type PlanLensStatus = "idle" | "loading" | "ok" | "unavailable" | "error";
export type PlanLensState = { status: PlanLensStatus; data: PlanLens | null; etag: string; error: string };
export type PlanLensEvent =
  | { type: "reset" } | { type: "start" } | { type: "ok"; data: PlanLens; etag: string } | { type: "same" }
  | { type: "unavailable" } | { type: "error"; message: string };
type Transport = (input: string, init: RequestInit) => Promise<Response>;

export const PLAN_LENS_LIMIT = 2 * 1024 * 1024;
export const IDLE: PlanLensState = { status: "idle", data: null, etag: "", error: "" };
const STAT_KEYS = ["areas", "cards", "withCode", "planned", "standalone", "unassigned"] as const;

export function planLensUrl(project: string, workspace: string, area: string | null) {
  return `/api/oporahub/plan-lens?${scopeQuery(area ? { project, workspace, area } : { project, workspace })}`;
}

/** Přísný parser obálky; neznámý tvar je chyba. */
export function parsePlanLens(raw: unknown): PlanLens {
  if (!isObject(raw) || raw.kind !== "plan") throw new Error("Lens plánu má neplatný tvar.");
  if (!isObject(raw.spec) || raw.spec.kind !== "graph") throw new Error("Lens plánu nenese graf PR Lens.");
  const stats = isObject(raw.stats) ? raw.stats : {};
  if (!STAT_KEYS.every(key => isCount(stats[key]))) throw new Error("Lens plánu má neplatná čísla.");
  const graphify = isObject(raw.graphify) ? raw.graphify : {};
  return {
    area: typeof raw.area === "string" && raw.area ? raw.area : null,
    digest: typeof raw.digest === "string" ? raw.digest.slice(0, 120) : "",
    spec: raw.spec,
    stats: Object.fromEntries(STAT_KEYS.map(key => [key, stats[key]])) as PlanStats,
    graphify: { available: graphify.available === true,
      sourceRevision: typeof graphify.sourceRevision === "string" && graphify.sourceRevision ? graphify.sourceRevision.slice(0, 64) : null },
  };
}

/** Jedno čtení: odpověď převede na událost stavu; obnova posílá ETag, takže beze změny přijde 304. */
export async function readPlanLens(url: string, etag: string, signal: AbortSignal,
  transport: Transport = (input, init) => fetch(input, init)): Promise<PlanLensEvent> {
  try {
    const response = await transport(url, { signal, cache: "no-store", redirect: "error", headers: etag ? { "If-None-Match": etag } : {} });
    if (response.status === 304) return { type: "same" };
    if (response.status === 404) return { type: "unavailable" };
    if (response.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event(ACCESS_REQUIRED_EVENT));
    if (!response.ok) return { type: "error", message: `Lens plánu není dostupný (HTTP ${response.status}).` };
    const raw = await response.text();
    if (raw.length > PLAN_LENS_LIMIT) return { type: "error", message: "Lens plánu překročil povolenou velikost." };
    return { type: "ok", data: parsePlanLens(JSON.parse(raw)), etag: response.headers.get("ETag") ?? "" };
  } catch (error) {
    if (signal.aborted) throw error;
    return { type: "error", message: error instanceof Error ? error.message : "Čtení Lens plánu se nezdařilo." };
  }
}

/** Stav čtení: načítání drží poslední data, 304 je potvrdí, 404 je klidný stav „není na serveru“. */
export function planLensReducer(state: PlanLensState, event: PlanLensEvent): PlanLensState {
  switch (event.type) {
    case "reset": return IDLE;
    case "start": return { ...state, status: "loading", error: "" };
    case "ok": return { status: "ok", data: event.data, etag: event.etag, error: "" };
    case "same": return state.data ? { ...state, status: "ok", error: "" } : { ...IDLE, status: "error", error: "Server potvrdil Lens plánu, který tu ještě není." };
    case "unavailable": return { ...IDLE, status: "unavailable" };
    case "error": return { ...state, status: "error", error: event.message };
  }
}
