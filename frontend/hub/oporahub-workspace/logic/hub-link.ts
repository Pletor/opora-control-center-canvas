import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";

/** Přímý odkaz do OporaHubu: `?environment=hub&ohView=agents` nebo `&ohCard=<nodeId>` (i pro agenty a snímky). */
export function initialHubLink(search: string): { tab: "overview" | "agents"; card: string } {
  const params = new URLSearchParams(search);
  return { tab: params.get("ohView") === "agents" ? "agents" : "overview", card: params.get("ohCard")?.slice(0, 200) ?? "" };
}
/** Výchozí karta pro záložku Karta: první karta, kterou agent-state nabízí k převzetí, jinak první karta plánu. */
export function defaultCard(state: AgentState | null, choices: { id: string }[]) {
  const offered = state?.actions.find(item => item.verb === "claim" && item.targetId && choices.some(card => card.id === item.targetId));
  return offered?.targetId ?? choices[0]?.id ?? "";
}
