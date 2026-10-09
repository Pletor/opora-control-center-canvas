// Původ rozhodnutí karet „z vN“: načte zamrazená kola (GET /api/desktop-v3/card-rounds) jen u karet
// v kole ≥ 2, které mají rozhodnutí, a vrátí mapu id rozhodnutí → kolo vzniku. Nic neukládá.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { CardRound, RoundsResponse } from "@/editor/node-detail/rounds/logic/rounds-model";
import { cardsWithRoundDecisions, decisionRounds } from "@/editor/node-detail/rounds/logic/rounds-model";

export function useDecisionRounds(project: string, workspace: string, decisions: { nodeId: string }[],
  nodes: Record<string, { round?: CardRound }>): Map<string, number> {
  const [origin, setOrigin] = useState<Map<string, number>>(() => new Map());
  // Klíč: karty v kole ≥ 2 a jejich čísla kol; nové kolo nebo nové rozhodnutí z dřívějšího kola načte znovu.
  const cards = cardsWithRoundDecisions(decisions, nodes);
  const key = cards.map((id) => `${id}:${nodes[id]?.round?.number ?? 1}`).join("|");
  useEffect(() => {
    let alive = true;
    if (!cards.length) { setOrigin(new Map()); return; }
    Promise.all(cards.map((nodeId) => api<RoundsResponse>("/api/desktop-v3/card-rounds?" + new URLSearchParams({ project, workspace, nodeId }))
      .then((value) => value.rounds).catch(() => [])))
      .then((lists) => { if (alive) setOrigin(decisionRounds(lists.flat())); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` shrnuje `cards`
  }, [project, workspace, key]);
  return origin;
}
