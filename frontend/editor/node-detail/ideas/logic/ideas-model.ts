// Čistý model podnětů k dalšímu vývoji karty (stav uzlu `ideas`). Podnět je ne-blokující nález review,
// kritika nebo člověka: etapu nezastaví, jen se zapamatuje na později. Agent ho přidá přes agent-output
// (`output.ideas`), odškrtnout a smazat smí jen člověk; server to hlídá (backend/editor/agent_memory/card_ideas.py).
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { withNode } from "@/editor/workflow/blocks/logic/block-model";

export type IdeaStatus = "open" | "done";
export type CardIdea = {
  id: string;
  text: string;
  /** Kdo podnět přidal: jméno relace agenta nebo „human“. */
  by: string;
  /** Odkud: human, agent, review, work, test, fix nebo critic:user|sly|hacker. */
  source: string;
  /** Etapa pipeline, při jejímž odevzdání podnět vznikl. */
  stageId?: string;
  at: string;
  status: IdeaStatus;
};

const SOURCE_LABEL: Record<string, string> = {
  human: "člověk", agent: "agent", review: "review", work: "práce", test: "test", fix: "oprava",
  "critic:user": "kritik: hodný uživatel", "critic:sly": "kritik: vyčuraný", "critic:hacker": "kritik: hacker",
};

export function sourceLabel(source: string): string {
  return SOURCE_LABEL[source] ?? source;
}

export function ideasOf(state: DesktopState, nodeId: string): CardIdea[] {
  return state.nodes[nodeId]?.ideas ?? [];
}

export function openIdeas(ideas: CardIdea[] | undefined): number {
  return (ideas ?? []).filter((idea) => idea.status === "open").length;
}

/** Pořadí v seznamu: otevřené nahoře (nejnovější první), odškrtnuté pod nimi. */
export function sortedIdeas(ideas: CardIdea[]): CardIdea[] {
  const rank = (idea: CardIdea) => (idea.status === "open" ? 0 : 1);
  return ideas.slice().sort((a, b) => rank(a) - rank(b) || b.at.localeCompare(a.at));
}

const withIdeas = (nodeId: string, fn: (ideas: CardIdea[]) => CardIdea[]) => (state: DesktopState) =>
  withNode(state, nodeId, (node) => {
    const next = fn(node.ideas ?? []);
    const { ideas: _dropped, ...rest } = node;
    return next.length ? { ...rest, ideas: next } : rest;
  });

/** Odškrtnutí (a jeho vrácení) dělá člověk jedním klikem. */
export const setIdeaStatus = (nodeId: string, id: string, status: IdeaStatus) =>
  withIdeas(nodeId, (ideas) => ideas.map((idea) => (idea.id === id ? { ...idea, status } : idea)));

export const removeIdea = (nodeId: string, id: string) =>
  withIdeas(nodeId, (ideas) => ideas.filter((idea) => idea.id !== id));
