import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import { STAGE_IDS, type AgentState, type Health, type StageId } from "./agent-state";

// Promítnutí smyčky etap do infografiky: pořadí, popisky, kdo krok dělá a poloha v „hadovi“.
export type Tone = "ok" | "warn" | "bad" | "gap";
export type Actor = "human" | "agent" | "both" | "system";
export const toneOf: Record<Health, Tone> = { ok: "ok", waiting: "warn", blocking: "bad", not_connected: "gap" };
/** Zdraví se nikdy nečte jen z odstínu: každý stav má vlastní tvar značky a slovo. */
export const healthGlyph: Record<Health, string> = { ok: "✓", waiting: "◷", blocking: "✕", not_connected: "◌" };
export const healthLabel: Record<Health, string> = { ok: "v pořádku", waiting: "čeká", blocking: "blokuje", not_connected: "nenapojeno" };
export const actorLabel: Record<Actor, string> = { human: "člověk", agent: "agent", both: "člověk + agent", system: "systém" };

const META: Record<StageId, { label: string; unit: string; actor: Actor; target: DetailTarget }> = {
  plan: { label: "Plán", unit: "karet", actor: "system", target: { kind: "graph", title: "Plán a návrhy grafu" } },
  proposal: { label: "Návrh změny", unit: "otevřené", actor: "both", target: { kind: "history", title: "Návrhy a historie" } },
  acceptance: { label: "Přijetí", unit: "čeká na vás", actor: "human", target: { kind: "acceptance", title: "Přijímání návrhů" } },
  claim: { label: "Převzetí", unit: "připraveno", actor: "agent", target: { kind: "budgets", title: "Pravidla a limity běhů" } },
  work: { label: "Práce", unit: "běží", actor: "agent", target: { kind: "executions", title: "Běhy agentů" } },
  evidence: { label: "Důkazy", unit: "nahlášeno", actor: "agent", target: { kind: "executions", title: "Nahlášené výsledky" } },
  review: { label: "Review", unit: "ke kontrole", actor: "human", target: { kind: "executions", title: "Kontrola výsledků" } },
  pull_request: { label: "PR / GitHub", unit: "PR navázáno", actor: "agent", target: { kind: "evidence", title: "Důkazy z GitHubu" } },
  merge: { label: "Merge", unit: "sloučeno", actor: "human", target: { kind: "tracking", title: "Sledování GitHubu" } },
  plan_writeback: { label: "Zápis do plánu", unit: "zapsáno", actor: "system", target: { kind: "history", title: "Historie plánu" } },
};

/** Strojové důvody (`reason`) v lidské češtině; neznámý kód se ukáže doslova, nikdy se nevymýšlí. */
export const reasonText: Record<string, string> = {
  empty_plan: "Plán zatím nemá karty.", no_accepted_baseline: "Chybí přijatý základ plánu.",
  working_differs_from_accepted: "Pracovní verze se liší od přijaté.", accepted_plan_current: "Pracovní verze odpovídá přijaté.",
  stale_proposals: "Některé návrhy stojí na starém základu.", proposals_current: "Návrhy stojí na aktuální hlavě.",
  no_pending_proposals: "Žádné otevřené návrhy.", baseline_awaiting_human: "Základ čeká na přijetí člověkem.",
  acceptance_overdue: "Návrh čeká déle než 24 h.", awaiting_human_within_window: "Čeká na člověka v limitu 24 h.",
  nothing_to_accept: "Nic nečeká na přijetí.", budget_exhausted: "Karta vyčerpala pokusy nebo opravy.",
  cards_ready: "Karty připravené k převzetí.", nothing_ready: "Žádná karta není připravená.",
  lease_past_deadline: "Běh je po termínu oprávnění.", runs_active: "Běhy v mezích oprávnění.", no_active_runs: "Nic neběží.",
  stale_evidence: "Výsledek patří jiné přijaté revizi.", evidence_reported: "Výsledky nahlášeny, neověřeny.",
  no_evidence: "Zatím žádné výsledky.", human_review_required: "Výsledek čeká na kontrolu člověkem.",
  nothing_to_review: "Nic ke kontrole.", pull_request_link_module_missing: "Vazba běh → PR zatím není napojena.",
  results_without_pull_request: "Výsledky bez navázaného PR.", results_linked: "Výsledky mají PR.",
  no_pull_requests: "Zatím žádné PR.", pull_requests_open: "PR čekají na merge.", merged: "PR sloučeno.",
  nothing_to_merge: "Nic ke sloučení.", writeback_not_reported: "Zápis do plánu se nehlásí.",
  merged_without_plan_writeback: "Sloučeno bez zápisu do plánu.", plan_written_back: "Plán aktualizován.",
  nothing_to_write_back: "Nic k zápisu.",
};

export type StageView = {
  id: StageId; n: number; label: string; unit: string; actor: Actor; count: number; health: Health; tone: Tone;
  reason: string; reasonText: string; row: number; col: number; target: DetailTarget;
};
export type Direction = "right" | "down" | "left" | "up";
export type ConnectorView = { from: StageId; to: StageId; label: string; dir: Direction; tone: "plain" | "warn" | "broken"; row: number; col: number };
const LINKS = ["návrh", "přijetí", "CAS hlavy", "heartbeat", "výsledek", "SHA", "revize + SHA", "merge", "zápis", "zpět do plánu"];

/** Had o dvou řadách: 1–5 zleva doprava, 6–10 zprava doleva; spojky leží v sudých sloupcích. */
function place(index: number) {
  return index < 5 ? { row: 1, col: index * 2 + 1 } : { row: 3, col: 9 - (index - 5) * 2 };
}
function connectorPlace(index: number): { row: number; col: number; dir: Direction } {
  if (index < 4) return { row: 1, col: index * 2 + 2, dir: "right" };
  if (index === 4) return { row: 2, col: 9, dir: "down" };
  if (index < 9) return { row: 3, col: 9 - (index - 5) * 2 - 1, dir: "left" };
  return { row: 2, col: 1, dir: "up" };
}

export type LoopItem = { kind: "stage"; stage: StageView } | { kind: "connector"; connector: ConnectorView };
/** Položky v pořadí čtení (DOM): etapa, spojka, etapa…; poslední spojka vrací smyčku do plánu. */
export function loopModel(state: AgentState): LoopItem[] {
  const stages = STAGE_IDS.map((id, index): StageView => {
    const value = state.stages.find(item => item.id === id)!;
    return { id, n: index + 1, ...META[id], count: value.count, health: value.health, tone: toneOf[value.health],
      reason: value.reason, reasonText: reasonText[value.reason] ?? value.reason, ...place(index) };
  });
  return stages.flatMap((stage, index): LoopItem[] => {
    const next = stages[(index + 1) % stages.length];
    const tone = stage.health === "not_connected" || next.health === "not_connected" ? "broken"
      : next.health === "blocking" || next.health === "waiting" ? "warn" : "plain";
    const label = tone === "broken" ? `${LINKS[index]} · nenapojeno` : LINKS[index];
    return [{ kind: "stage", stage }, { kind: "connector", connector: { from: stage.id, to: next.id, label, tone, ...connectorPlace(index) } }];
  });
}
