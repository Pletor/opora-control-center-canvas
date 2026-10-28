// Strážci ve Velínu (docs/strazci.md §5): jeden řádek „Strážci ✓ / ⚠ N“ z `GET /api/strazci?project=` a seznam
// otevřených nálezů z agent-state `guards.findings`. Strážce `mapa` se nepočítá: jeho díry ukazuje řádek „Díry mapy“
// (jeden zdroj děr mapy). Čisté funkce, žádné odhady: chybějící pole = starší server, nic se nekreslí.
import type { AgentGuardFinding, AgentState, GuardSeverity } from "@/hub/oporahub-agent-state/logic/agent-state";

export type GuardOpen = Record<GuardSeverity, number>;
export type GuardStatusItem = {
  id: string; label: string; every_s: number; lastRunAt: string | null; lastOkAt: string | null; lastError?: string; open: GuardOpen;
};
export type GuardStatus = { guards: GuardStatusItem[]; open: GuardOpen };
export type GuardLine = { ok: boolean; count: number; lastRunAt: string | null; errors: { id: string; label: string; error: string }[] };
export type VelinGuardItem = AgentGuardFinding & { cardName: string };

const MAP_GUARD = "mapa";
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const count = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0;
const open = (value: unknown): value is GuardOpen => object(value) && count(value.block) && count(value.warn) && count(value.info);

/** Ověří odpověď `GET /api/strazci`; neplatná = null (řádek se neukáže, nic se nevymýšlí). */
export function parseGuardStatus(raw: unknown): GuardStatus | null {
  if (!object(raw) || !open(raw.open) || !Array.isArray(raw.guards)) return null;
  const valid = raw.guards.every(item => object(item) && typeof item.id === "string" && typeof item.label === "string"
    && open(item.open) && (item.lastRunAt === null || typeof item.lastRunAt === "string")
    && (item.lastError === undefined || typeof item.lastError === "string"));
  return valid ? raw as unknown as GuardStatus : null;
}

/** Řádek strážců: ✓ bez chyby strážce a bez otevřeného nálezu block/warn mimo mapu; jinak ⚠ s počtem a chybami. */
export function guardLine(status: GuardStatus): GuardLine {
  const watched = status.guards.filter(item => item.id !== MAP_GUARD);
  const total = watched.reduce((sum, item) => sum + item.open.block + item.open.warn, 0);
  const errors = status.guards.filter(item => item.lastError).map(item => ({ id: item.id, label: item.label, error: item.lastError! }));
  const runs = status.guards.map(item => item.lastRunAt).filter((value): value is string => !!value).sort();
  return { ok: !total && !errors.length, count: total, lastRunAt: runs[runs.length - 1] ?? null, errors };
}

/** Otevřené nálezy z agent-state (pořadí serveru: block první) se jménem karty; mapu server vynechal, tady pojistka. */
export function guardFindings(state: AgentState, nameOf: (id: string) => string): VelinGuardItem[] | null {
  if (!state.guards) return null;
  return state.guards.findings.filter(item => item.guard !== MAP_GUARD)
    .map(item => ({ ...item, cardName: item.nodeId ? nameOf(item.nodeId) : "" }));
}

export const SEVERITY_GLYPH: Record<GuardSeverity, string> = { block: "✕", warn: "⚠", info: "i" };
export const SEVERITY_LABEL: Record<GuardSeverity, string> = { block: "blokuje", warn: "varování", info: "informace" };
