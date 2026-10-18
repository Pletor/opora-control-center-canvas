// Hlavičky skupin v přepínači disciplín (Kreslení · Logika · Provoz) jako záložky: otevřená je jen skupina vybrané
// disciplíny, ostatní ukazují počet zapnutých neuronů a kolik věcí v nich čeká na člověka. „Čeká na tebe“ proklikává
// disciplíny, kde na člověka něco čeká (stejné položky jako seznam v Přehledu, `waitingOnHuman`). Bez Reactu.
import type { Feedback, VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { UNASSIGNED, filterByDiscipline, type Discipline, type DisciplineGroup, type DisciplineView } from "./disciplines";
import { waitingOnHuman } from "./vault-dock-model";

export type WaitingCounts = Record<DisciplineView, number>;

/** Kolik věcí čeká na člověka v každé zapnuté disciplíně a v Nezařazených (strom zúžený stejně jako pohled). */
export function waitingByDiscipline(roots: VaultNode[], live: Discipline[], feedback: Feedback[] = []): WaitingCounts {
  const out: WaitingCounts = {};
  for (const id of [...live.map((item) => item.id), UNASSIGNED]) {
    out[id] = waitingOnHuman(filterByDiscipline(roots, id), feedback).length;
  }
  return out;
}

/** Otevřená skupina = skupina vybrané disciplíny; Nezařazené žádnou skupinu neotvírají. */
export const activeGroup = (view: DisciplineView, live: Discipline[]): DisciplineGroup | null =>
  live.find((item) => item.id === view)?.group ?? null;

/** Součet „čeká na tebe“ přes disciplíny skupiny. */
export const groupWaiting = (group: DisciplineGroup, live: Discipline[], waiting: WaitingCounts): number =>
  live.filter((item) => item.group === group).reduce((sum, item) => sum + (waiting[item.id] ?? 0), 0);

export const totalWaiting = (waiting: WaitingCounts): number => Object.values(waiting).reduce((sum, n) => sum + n, 0);

/**
 * Klik na hlavičku skupiny vybere disciplínu, kde na člověka něco čeká; jinak první s obsahem v rozsahu; jinak první
 * zapnutou. Spící skupina (bez živé disciplíny) nemá kam vést → `null`.
 */
export function groupTarget(group: DisciplineGroup, live: Discipline[], counts: Record<DisciplineView, number>, waiting: WaitingCounts): DisciplineView | null {
  const items = live.filter((item) => item.group === group);
  return items.find((item) => (waiting[item.id] ?? 0) > 0)?.id
    ?? items.find((item) => (counts[item.id] ?? 0) > 0)?.id
    ?? items[0]?.id ?? null;
}

/** Proklik „Čeká na tebe“: další disciplína v pořadí tabulky (dokola, Nezařazené na konci), kde něco čeká; žádná → `null`. */
export function nextWaiting(view: DisciplineView, live: Discipline[], waiting: WaitingCounts): DisciplineView | null {
  const order = [...live.map((item) => item.id), UNASSIGNED];
  const start = order.indexOf(view);
  for (let step = 1; step <= order.length; step += 1) {
    const id = order[(start + step) % order.length];
    if ((waiting[id] ?? 0) > 0) return id;
  }
  return null;
}
