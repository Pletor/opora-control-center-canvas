import type { Health } from "./agent-state";
import { REVIEW_GATE_REASONS } from "./review-gate-labels";

// Zdraví etapy a karty jako značka a slovo a strojové důvody (`reason`) v češtině; sdílí je drawer karty,
// tvář karty na plátně a značka zdraví. Smyčka etap (dřív `hub/oporahub-loop`) je smazaná (docs/navrhy/2026-11-03-novy-zaklad.md §4).
/** Zdraví se nikdy nečte jen z odstínu: každý stav má vlastní tvar značky a slovo. */
export const healthGlyph: Record<Health, string> = { ok: "✓", waiting: "◷", blocking: "✕", not_connected: "◌" };
export const healthLabel: Record<Health, string> = { ok: "v pořádku", waiting: "čeká", blocking: "blokuje", not_connected: "nenapojeno" };

/** Strojové důvody (`reason`) v lidské češtině; neznámý kód se ukáže doslova, nikdy se nevymýšlí. */
export const reasonText: Record<string, string> = {
  empty_plan: "Plán zatím nemá karty.", no_accepted_baseline: "Chybí přijatý základ plánu.",
  working_differs_from_accepted: "Pracovní verze se liší od přijaté.", accepted_plan_current: "Pracovní verze odpovídá přijaté.",
  read_only_architecture: "Main nese jen architekturu; karty a přijetí jsou v pracovním prostoru.",
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
  nothing_to_write_back: "Nic k zápisu.", auto_rebase_conflicts: "Auto-rebase našel konflikt stejného pole.",
  card_closed: "Karta uzavřena.", awaiting_human_close: "PR sloučeno; kartu uzavře server po splnění definice hotovo.",
  card_in_plan: "Karta je v přijatém plánu.", budget_policy_required: "Karta potřebuje pravidla běhů.",
  ...REVIEW_GATE_REASONS,
};
