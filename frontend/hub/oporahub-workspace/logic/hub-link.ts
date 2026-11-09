import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";

/** Přímý odkaz do OporaHubu: `?environment=hub&ohView=agents` (nebo `ohView=process` pro Živý proces). Detail karty (`?ohCard=<id>&ohTab=`) čte
 *  jednotný drawer `hub/oporahub-card-drawer` sám, v jakémkoli prostředí. */
export function initialHubLink(search: string): { tab: "process" | "agents" } {
  return { tab: new URLSearchParams(search).get("ohView") === "agents" ? "agents" : "process" };
}
/** The existing content review accepts only an exact, matching scope deep link. */
export function scopedContentLink(search: string, project: string, workspace: string) {
  const query = new URLSearchParams(search), id = query.get("ohContent");
  return query.get("project") === project && query.get("workspace") === workspace && id && /^[a-f0-9]{40}$/.test(id) ? id : null;
}
/** Výchozí karta pro tlačítko Karta: první karta, kterou agent-state nabízí k převzetí, jinak první karta plánu. */
export function defaultCard(state: AgentState | null, choices: { id: string }[]) {
  const offered = state?.actions.find(item => item.verb === "claim" && item.targetId && choices.some(card => card.id === item.targetId));
  return offered?.targetId ?? choices[0]?.id ?? "";
}
