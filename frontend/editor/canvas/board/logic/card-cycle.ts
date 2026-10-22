// Odmítnutý cyklus v grafu karet (docs/oporahub-agent-state.md, „Graf karet“): uložení, které přidá vazbu
// `next` uzavírající cyklus, server vrátí 409 `card_cycle` s cestou id karet. Člověk má vidět, KTERÉ karty
// cyklus tvoří, jmény a v pořadí; vazba se neuloží a plátno zůstane, jak bylo.
import { ApiError } from "@/shared/types/logic/types";

/** Čitelná chyba cyklu („A → B → A“), nebo `null`, když nejde o odmítnutý cyklus. */
export function cardCycleError(error: unknown, nameOf: (id: string) => string | undefined): Error | null {
  if (!(error instanceof ApiError) || error.status !== 409 || error.body.code !== "card_cycle") return null;
  const cycle = Array.isArray(error.body.cycle) ? error.body.cycle.filter((id): id is string => typeof id === "string") : [];
  const path = cycle.map((id) => nameOf(id) || id).join(" → ");
  return new Error(`Vazba „další krok“ by uzavřela cyklus karet${path ? `: ${path}` : ""}. Graf závislostí musí zůstat bez cyklů, nic se neuložilo.`);
}
