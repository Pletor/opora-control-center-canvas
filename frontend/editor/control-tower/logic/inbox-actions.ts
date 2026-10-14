// Přímé akce fronty „Čeká na tebe“ bez Reactu: které návrhy jdou potvrdit hromadně za sektor a stavový
// automat tlačítka „Potvrdit“. Potvrzení je nevratné (kartu znovu otevře jen nové kolo), proto tlačítko
// chce dvojí klik: první ho na `ARM_MS` „natáhne“, teprve druhý v tom okně akci spustí. Žádný confirm()
// dialog, aby šel Velín ovládat i automatizovaně.
import type { InboxItem } from "./tower-model";

export const ARM_MS = 4000;

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

export type ConfirmState =
  | { kind: "idle" }
  | { kind: "armed"; until: number }
  | { kind: "busy" }
  | { kind: "error"; message: string };

export type ConfirmEvent =
  | { type: "click" }
  | { type: "tick" }
  | { type: "success" }
  | { type: "failure"; message: string };

export const idleConfirm = (): ConfirmState => ({ kind: "idle" });

/**
 * Jeden krok automatu: idle → armed(do now+ARM_MS) → busy → idle / error. `run` říká, že se má právě
 * teď spustit akce (druhý klik v čase). Klik po vypršení natáhne znovu; klik během ukládání nic nedělá;
 * `tick` po vypršení vrátí natažené tlačítko do klidu.
 */
export function confirmStep(state: ConfirmState, now: number, event: ConfirmEvent = { type: "click" }): { state: ConfirmState; run: boolean } {
  switch (event.type) {
    case "click":
      if (state.kind === "busy") return { state, run: false };
      if (state.kind === "armed" && now <= state.until) return { state: { kind: "busy" }, run: true };
      return { state: { kind: "armed", until: now + ARM_MS }, run: false };
    case "tick":
      return { state: state.kind === "armed" && now > state.until ? idleConfirm() : state, run: false };
    case "success":
      return { state: idleConfirm(), run: false };
    case "failure":
      return { state: { kind: "error", message: event.message || "Potvrzení se neuložilo." }, run: false };
  }
}

/** Popisek tlačítka podle stavu; `base` je klidový text („Potvrdit“, „Potvrdit vše v sektoru (3)“). */
export function confirmLabel(state: ConfirmState, base: string): string {
  if (state.kind === "armed") return "Opravdu potvrdit";
  if (state.kind === "busy") return "ukládám…";
  return base;
}
