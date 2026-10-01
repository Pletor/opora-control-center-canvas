/**
 * Konverzace k vykreslení: zprávy a chyby zůstávají samostatně, po sobě jdoucí volání nástrojů se
 * sbalí do jedné skupiny „3 kroky (Read, Grep, Skill)“. Čistá funkce bez Reactu.
 */
import type { ChatItem } from "./assistant-events";

export type ToolItem = Extract<ChatItem, { kind: "tool" }>;

export type ConversationEntry =
  | { kind: "message"; item: Extract<ChatItem, { kind: "message" }> }
  | { kind: "error"; item: Extract<ChatItem, { kind: "error" }> }
  | { kind: "steps"; id: string; tools: ToolItem[] };

export function groupEntries(items: ChatItem[]): ConversationEntry[] {
  const out: ConversationEntry[] = [];
  for (const item of items) {
    if (item.kind === "tool") {
      const last = out[out.length - 1];
      if (last && last.kind === "steps") last.tools.push(item);
      else out.push({ kind: "steps", id: `steps-${item.id}`, tools: [item] });
    } else if (item.kind === "error") out.push({ kind: "error", item });
    else out.push({ kind: "message", item });
  }
  return out;
}

function stepsWord(count: number): string {
  if (count === 1) return "krok";
  return count < 5 ? "kroky" : "kroků";
}

/** „3 kroky (Read, Grep, Skill)“: jména bez opakování v pořadí prvního výskytu. */
export function stepsLabel(tools: ToolItem[]): string {
  const names = [...new Set(tools.map((t) => t.name))];
  const shown = names.length > 4 ? [...names.slice(0, 4), "…"] : names;
  return `${tools.length} ${stepsWord(tools.length)} (${shown.join(", ")})`;
}

/** Souhrn stavu skupiny: běží, když něco běží; jinak počet chyb. */
export function stepsState(tools: ToolItem[]): { running: boolean; errors: number } {
  return { running: tools.some((t) => t.status === "running"), errors: tools.filter((t) => t.status === "error").length };
}
