// Data pro členění konverzace a osnovu: tahy, právě čtený tah, otázky z poslední odpovědi, souhrn
// kroků a kontext, který panel naposledy poslal se zprávou (per úkol, jen v paměti panelu). Skládá
// čisté funkce z turns.ts a decisions.ts; volá ho jen AssistantPanel.
import { useCallback, useMemo, useState } from "react";
import type { AssistantContext } from "./assistant-api";
import type { ChatItem } from "./assistant-events";
import { parseDecisions, type Decision } from "./decisions";
import { buildTurns, decisionAnchor, lastAnswer, stepsSummary, type Turn } from "./turns";
import { scrollToAnchor } from "./use-active-turn";

export type OutlineDecisions = { anchorOf: (questionId: string) => string; questions: Decision[] };

export type TaskOutline = {
  turns: Turn[];
  activeTurn: string | null;
  setActiveTurn: (anchor: string | null) => void;
  decisions: OutlineDecisions | null;
  steps: { steps: number; denied: number } | null;
  /** Kontext naposledy odeslaný do aktivního úkolu, nebo null. */
  sentContext: AssistantContext | null;
  rememberSent: (sessionId: string, context: AssistantContext) => void;
  /** Plynulý posun na tah nebo kartu otázky. */
  jump: (anchor: string) => void;
};

export function useTaskOutline(items: ChatItem[], activeId: string | null): TaskOutline {
  const turns = useMemo(() => buildTurns(items), [items]);
  const [activeTurn, setActiveTurn] = useState<string | null>(null);
  const [sent, setSent] = useState<Record<string, AssistantContext>>({});
  const answer = useMemo(() => lastAnswer(items), [items]);
  const decisions = useMemo<OutlineDecisions | null>(() => {
    const set = answer ? parseDecisions(answer.text) : null;
    return answer && set ? { questions: set.questions, anchorOf: (q) => decisionAnchor(answer.id, q) } : null;
  }, [answer]);
  const steps = useMemo(() => stepsSummary(turns), [turns]);
  const rememberSent = useCallback((id: string, context: AssistantContext) => setSent((all) => ({ ...all, [id]: context })), []);
  const jump = useCallback((anchor: string) => {
    scrollToAnchor(anchor);
    if (turns.some((t) => t.anchor === anchor)) setActiveTurn(anchor);
  }, [turns]);
  return { turns, activeTurn, setActiveTurn, decisions, steps, sentContext: activeId ? sent[activeId] ?? null : null, rememberSent, jump };
}
