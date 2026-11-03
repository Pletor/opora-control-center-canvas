import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import type { AgentAction } from "./agent-state";

// Cíl akce agent-state v OporaHubu (fronta akcí v záložce Pro agenty). Horní pás přehledu zmizel se smyčkou etap.
/** Cíl rozhodnutí nebo akce se odvozuje z jejího API, ne z hádání: cesta říká druh návrhu. */
export function actionTarget(action: Pick<AgentAction, "path" | "targetId">, title: string): DetailTarget {
  const id = action.targetId ?? undefined;
  if (action.path.includes("/changesets/")) return { kind: "changes", id, title };
  if (action.path.includes("/graph-proposals/")) return { kind: "graph", id, title };
  if (action.path.includes("/content-changes/")) return { kind: "content", id, title };
  if (action.path.includes("/auto-rebase/conflicts/")) return { kind: "conflicts", id, title };
  if (action.path.includes("/verifications/")) return { kind: "formal", id, title };
  if (action.path.includes("/review-recurring/")) return { kind: "review-metrics", title };
  if (action.path.includes("/review-jobs/") || action.path.startsWith("github:")) return action.path.includes("/claim")
    ? { kind: "policy", title } : { kind: "executions", id, title };
  if (action.path.includes("/executions/claim") || action.path.includes("/desktop-v3/state")) return { kind: "card", id, title };
  if (action.path.includes("/executions/")) return { kind: "executions", id, title };
  return { kind: "graph", title };
}
