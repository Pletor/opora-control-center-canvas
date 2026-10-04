/**
 * Rozsah práce asistenta slovy (docs/asistent.md §6.1): „Celý obraz“ pracuje nad celým plátnem,
 * „Výběr“ jen nad vybranými uzly. U Výběru panel říká, kolik uzlů je vybráno. Čisté funkce.
 */
import type { AssistantScope } from "./assistant-api";

export const SCOPE_LABEL: Record<AssistantScope, string> = { selection: "Výběr", board: "Celý obraz" };

function nodesWord(count: number): string {
  if (count === 1) return "uzel";
  return count >= 2 && count <= 4 ? "uzly" : "uzlů";
}

/** „Výběr: 2 uzly“, bez výběru „nic nevybráno“. */
export function selectionLabel(count: number): string {
  return count > 0 ? `Výběr: ${count} ${nodesWord(count)}` : "nic nevybráno";
}
