// Přímé akce fronty „Čeká na tebe“ bez Reactu: které návrhy jdou potvrdit hromadně za sektor, stavový
// automat tlačítka „Potvrdit“ a samotné (sekvenční) potvrzování. Potvrzení je nevratné (kartu znovu
// otevře jen nové kolo), proto tlačítko chce dvojí klik: první ho na `ARM_MS` natáhne a zapamatuje si
// rozsah (id karet), druhý — nejdřív po `ARM_GUARD_MS`, aby dvojklik nepotvrdil omylem — potvrdí právě
// ten rozsah. Změní-li se mezitím seznam, natažení se zruší. Žádný confirm() dialog (automatizace).
import type { InboxItem } from "./tower-model";

export const ARM_MS = 8000;
export const ARM_GUARD_MS = 500;

/** Návrhy uzavření (`proposed`) podle sektoru, v pořadí fronty; položky mimo sektor se vynechají. */
export function proposalsBySector(items: InboxItem[]): Map<string, string[]> {
  const result = new Map<string, string[]>();
  for (const item of items) {
    if (item.kind !== "proposed" || !item.sectorId) continue;
    const list = result.get(item.sectorId);
    if (!list) result.set(item.sectorId, [item.nodeId]);
    else if (!list.includes(item.nodeId)) list.push(item.nodeId);
  }
  return result;
}

/** Stejný rozsah (pořadí nehraje roli). */
export function sameScope(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false;
  const set = new Set(a);
  return b.every((id) => set.has(id));
}

/** Kříží se rozsah tlačítka s kartami, které se právě potvrzují? */
export function scopeLocked(scope: readonly string[], busy: ReadonlySet<string>): boolean {
  return scope.some((id) => busy.has(id));
}

export type ConfirmResult = { ok: string[]; failed: { id: string; error: string }[] };

export type ConfirmState =
  | { kind: "idle" }
  | { kind: "armed"; since: number; until: number; scope: string[] }
  | { kind: "busy"; scope: string[] }
  | { kind: "stale" }
  | { kind: "error"; message: string }
  | { kind: "done"; message: string };

export type ConfirmEvent =
  | { type: "click"; scope: string[] }
  | { type: "scope"; scope: string[] }
  | { type: "tick" }
  | { type: "result"; message: string; failed: boolean }
  | { type: "failure"; message: string };

export const idleConfirm = (): ConfirmState => ({ kind: "idle" });

/**
 * Jeden krok automatu: idle → armed(rozsah, do now+ARM_MS) → busy → idle / done / error.
 * `run` je rozsah, který se má právě teď potvrdit (druhý klik v čase a se stejným rozsahem), jinak `null`.
 * Klik dřív než ARM_GUARD_MS po natažení i klik během ukládání nic nedělá; klik po vypršení natáhne znovu;
 * změna rozsahu natažené tlačítko zruší (`stale`); `tick` po vypršení vrátí natažené tlačítko do klidu.
 */
export function confirmStep(state: ConfirmState, now: number, event: ConfirmEvent): { state: ConfirmState; run: string[] | null } {
  const arm = (scope: string[]): ConfirmState => ({ kind: "armed", since: now, until: now + ARM_MS, scope: [...scope] });
  switch (event.type) {
    case "click":
      if (state.kind === "busy" || !event.scope.length) return { state, run: null };
      if (state.kind === "armed" && now <= state.until) {
        if (now < state.since + ARM_GUARD_MS) return { state, run: null };
        if (!sameScope(state.scope, event.scope)) return { state: { kind: "stale" }, run: null };
        return { state: { kind: "busy", scope: state.scope }, run: state.scope };
      }
      return { state: arm(event.scope), run: null };
    case "scope":
      return { state: state.kind === "armed" && !sameScope(state.scope, event.scope) ? { kind: "stale" } : state, run: null };
    case "tick":
      return { state: state.kind === "armed" && now > state.until ? idleConfirm() : state, run: null };
    case "result":
      if (!event.message) return { state: idleConfirm(), run: null };
      return { state: event.failed ? { kind: "error", message: event.message } : { kind: "done", message: event.message }, run: null };
    case "failure":
      return { state: { kind: "error", message: event.message || "Potvrzení se neuložilo." }, run: null };
  }
}

/** Popisek tlačítka; `armed` je text nataženého stavu s rozsahem („Opravdu uzavřít „X“?“). */
export function confirmLabel(state: ConfirmState, base: string, armed: string): string {
  if (state.kind === "armed") return armed;
  if (state.kind === "busy") return "ukládám…";
  if (state.kind === "stale") return "Seznam se změnil, klikni znovu";
  return base;
}

const cards = (n: number) => n + " " + (n === 1 ? "kartu" : n >= 2 && n <= 4 ? "karty" : "karet");

/** Text nataženého tlačítka podle rozsahu. */
export function armedText(scope: readonly string[], nameOf: (id: string) => string, inSector: boolean): string {
  if (scope.length === 1 && !inSector) return "Opravdu uzavřít „" + nameOf(scope[0]) + "“?";
  return "Opravdu uzavřít " + cards(scope.length) + " v sektoru?";
}

/** Hláška po potvrzení: prázdná, když prošla jediná karta (zmizí sama); jinak „Uzavřeno 2, selhalo 1: X — chyba“. */
export function confirmSummary(result: ConfirmResult, nameOf: (id: string) => string): string {
  if (!result.failed.length && result.ok.length <= 1) return "";
  const head = "Uzavřeno " + result.ok.length + (result.failed.length ? ", selhalo " + result.failed.length : "");
  if (!result.failed.length) return head + ".";
  return head + ": " + result.failed.map((f) => nameOf(f.id) + " — " + f.error).join("; ");
}

type ConfirmOne = (id: string) => Promise<boolean>;
type ConfirmMany = (sectorId: string, ids: string[]) => Promise<void>;

/**
 * Potvrdí rozsah: s `confirmOne` po kartách postupně (jedna chyba nezastaví ostatní, `false` = neuloženo),
 * jinak jedním hromadným `confirmMany` za sektor (uspěje nebo selže celé). Nikdy nevyhodí.
 */
export async function runConfirm(ids: string[], sectorId: string, confirmOne?: ConfirmOne, confirmMany?: ConfirmMany): Promise<ConfirmResult> {
  const result: ConfirmResult = { ok: [], failed: [] };
  if (confirmOne) {
    for (const id of ids) {
      try {
        if (await confirmOne(id)) result.ok.push(id);
        else result.failed.push({ id, error: "neuloženo" });
      } catch (error) {
        result.failed.push({ id, error: String(error) });
      }
    }
    return result;
  }
  if (!confirmMany || !sectorId) return { ok: [], failed: ids.map((id) => ({ id, error: "potvrzení tu není k dispozici" })) };
  try {
    await confirmMany(sectorId, ids);
    return { ok: [...ids], failed: [] };
  } catch (error) {
    return { ok: [], failed: ids.map((id) => ({ id, error: String(error) })) };
  }
}
