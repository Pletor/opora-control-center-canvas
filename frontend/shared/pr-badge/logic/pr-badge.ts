// Odznak PR karty v barvách GitHubu: z faktu agent-state (`cards[].pr`, docs/oporahub-agent-state.md) udělá tón
// a slovo. Čistá funkce bez Reactu; plátno i Velín kreslí totéž. Uzavřená karta (`done.confirmed`) odznak nemá,
// její ztlumený vzhled stačí. Starší server bez `pr`: etapa sama řekne aspoň „sloučeno“ / „otevřené“ bez čísla.
export type PrState = "open" | "merged" | "closed";
export type PrLink = { number: number | null; state: PrState };
export type PrBadge = { tone: PrState; label: string };

const LABEL: Record<PrState, (pr: string) => string> = {
  merged: pr => pr ? `Sloučeno · ${pr}` : "Sloučeno",
  open: pr => pr ? `${pr} otevřené` : "PR otevřené",
  closed: pr => pr ? `${pr} zavřené bez sloučení` : "PR zavřené bez sloučení",
};

/** Stav PR z etapy, když server `pr` nepošle (jen jednoznačné důvody). */
function fromStage(stage: string, reason: string): PrState | null {
  if (stage === "merge" && reason === "awaiting_human_close") return "merged";
  if (stage === "pull_request" && reason === "pull_requests_open") return "open";
  return null;
}

/** `{tone, label}` odznaku, nebo null (karta bez PR nebo uzavřená). */
export function prBadge(stage: string, reason: string, link: PrLink | null | undefined, closed: boolean): PrBadge | null {
  if (closed || reason === "card_closed") return null;
  const state = link?.state ?? fromStage(stage, reason);
  if (!state || !LABEL[state]) return null;
  const number = link?.number;
  return { tone: state, label: LABEL[state](typeof number === "number" ? `PR #${number}` : "") };
}
