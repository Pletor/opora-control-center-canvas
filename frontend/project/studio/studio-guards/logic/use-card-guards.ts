// Nálezy strážců po kartách ze sdíleného snímku agent-state (`useAgentState`, stejné čtení jako přehled a plátno).
// Snímek se obnovuje často; mapa se mění jen tehdy, když se změní samotné nálezy, aby stav karet zbytečně nepřepočítával.
import { useMemo } from "react";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import { guardsByNode, guardsKey, type GuardTally } from "./guard-tally";

export function useCardGuards(project: string, workspace: string): Map<string, GuardTally> {
  const key = guardsKey(guardsByNode(useAgentState(project, workspace).state?.cards));
  return useMemo(() => new Map<string, GuardTally>(key ? JSON.parse(key) : []), [key]);
}
