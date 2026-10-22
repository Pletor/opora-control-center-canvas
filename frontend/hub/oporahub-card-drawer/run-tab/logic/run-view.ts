import type { BudgetContext } from "@/hub/execution-budgets/logic/execution-budgets";
import type { ExecutionSummary } from "@/hub/execution-receipts/logic/execution-receipts";
import type { GateSelfChecks } from "@/hub/oporahub-review-gate/logic/review-gate";

// Záložka Běh: lease s odpočtem, rozpočet pokusů a oprav a samokontroly agenta. Čas serveru a klienta se
// srovná jedním posunem (serverNow při načtení), takže odpočet neutíká s hodinami prohlížeče.
export type LeaseView = { state: "active" | "expired" | "closed" | "none"; remaining: number; fraction: number; label: string; text: string };

export const clock = (seconds: number) => {
  const total = Math.max(0, Math.floor(seconds)), hours = Math.floor(total / 3600), minutes = Math.floor(total / 60) % 60, rest = total % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return hours ? `${hours}:${pad(minutes)}:${pad(rest)}` : `${pad(minutes)}:${pad(rest)}`;
};

/** Nejnovější běh karty: běžící má přednost, jinak poslední podle času založení. */
export function latestExecution(executions: ExecutionSummary[], nodeId: string): ExecutionSummary | null {
  const mine = executions.filter(item => item.nodeId === nodeId);
  return mine.find(item => item.state === "running") ?? [...mine].sort((a, b) => (b.createdAt ?? "").localeCompare(a.createdAt ?? "") || b.epoch - a.epoch)[0] ?? null;
}

/** Odpočet lease: `nowSeconds` je čas klienta, `loadedAt` čas klienta při načtení s daným `serverNow`. */
export function leaseView(execution: ExecutionSummary | null, nowSeconds: number, loadedAt: number): LeaseView {
  if (!execution) return { state: "none", remaining: 0, fraction: 0, label: "—", text: "Karta zatím nemá běh." };
  if (execution.state !== "running") return { state: "closed", remaining: 0, fraction: 0, label: "—", text: `Běh skončil (${execution.state}).` };
  if (!Number.isFinite(execution.expiresAt) || !Number.isFinite(execution.serverNow)) return { state: "none", remaining: 0, fraction: 0, label: "?", text: "Termín lease není doložen." };
  const serverNow = execution.serverNow + Math.max(0, nowSeconds - loadedAt);
  const remaining = Math.max(0, execution.expiresAt - serverNow);
  // Délka lease není v souhrnu běhu; pruh ukazuje zbytek proti stavu při načtení (heartbeat ho zase doplní).
  const window = Math.max(remaining, execution.expiresAt - execution.serverNow);
  return { state: remaining > 0 ? "active" : "expired", remaining, fraction: window > 0 ? Math.min(1, remaining / window) : 0, label: clock(remaining),
    text: remaining > 0 ? `epocha ${execution.epoch} · konec ${new Date(execution.expiresAt * 1000).toLocaleTimeString("cs-CZ")}` : "Lease vypršela; kartu může převzít jiný běh." };
}

export type Meter = { key: string; label: string; used: number | null; max: number | null; text: string; tone: "ok" | "warn" | "bad" | "gap" };
const meter = (key: string, label: string, used: number | null, max: number | null, unit = ""): Meter => {
  const known = used !== null && max !== null && max > 0, share = known ? used / max : 0;
  return { key, label, used, max, text: known ? `${used} / ${max}${unit}` : "neznámé", tone: !known ? "gap" : share >= 1 ? "bad" : share >= 0.6 ? "warn" : "ok" };
};

/** Rozpočet běhu: pokusy a opravy z pravidel karty, čas od přijetí běhu proti jeho neměnnému stropu. */
export function budgetMeters(budget: BudgetContext | null, execution: ExecutionSummary | null, nowServer: number | null): Meter[] {
  const limits = budget?.policy?.limits ?? null, runMax = execution?.budget?.maxRunSeconds ?? null;
  const admitted = execution?.budget?.admittedAt;
  const used = runMax !== null && nowServer !== null && Number.isFinite(admitted) ? Math.max(0, Math.round((nowServer - (admitted as number)) / 60)) : null;
  return [meter("attempts", "Pokusy", budget?.attemptsUsed ?? null, limits?.maxAttempts ?? null),
    meter("repairs", "Opravy", budget?.repairRoundsUsed ?? null, limits?.maxRepairRounds ?? null),
    meter("time", "Čas", used, runMax !== null ? Math.round(runMax / 60) : null, " min")];
}

export type CheckChip = { name: string; state: "ok" | "failed" | "missing" };
/** Samokontroly z brány review: povinné, chybějící a selhané; bez brány prázdný seznam. */
export function selfCheckChips(checks: GateSelfChecks | undefined, required: Record<string, string> | undefined): CheckChip[] {
  if (!checks) return [];
  const names = new Set([...Object.keys(required ?? {}), ...checks.missing, ...checks.failed]);
  return [...names].sort().map(name => ({ name, state: checks.failed.includes(name) ? "failed" : checks.missing.includes(name) ? "missing" : "ok" }));
}
