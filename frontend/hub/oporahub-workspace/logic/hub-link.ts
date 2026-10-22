import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";

/** Přímý odkaz do OporaHubu: `?environment=hub&ohView=agents`. Detail karty (`?ohCard=<id>&ohTab=`) čte
 *  jednotný drawer `hub/oporahub-card-drawer` sám, v jakémkoli prostředí. */
export function initialHubLink(search: string): { tab: "overview" | "agents" } {
  const params = new URLSearchParams(search);
  return { tab: params.get("ohView") === "agents" ? "agents" : "overview" };
}
/** Výchozí karta pro tlačítko Karta: první karta, kterou agent-state nabízí k převzetí, jinak první karta plánu. */
export function defaultCard(state: AgentState | null, choices: { id: string }[]) {
  const offered = state?.actions.find(item => item.verb === "claim" && item.targetId && choices.some(card => card.id === item.targetId));
  return offered?.targetId ?? choices[0]?.id ?? "";
}
