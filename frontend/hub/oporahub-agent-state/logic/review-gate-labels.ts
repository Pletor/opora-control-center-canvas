// Popisky pravidel brány merge (docs/oporahub-review-jobs.md, „Pravidla brány“) pro etapu Review a frontu akcí.
// Kód důvodu je smlouva backendu; tady je jen jeho lidské znění.
export const REVIEW_GATE_REASONS: Record<string, string> = {
  review_gate_blocked: "Brána merge blokuje.", review_gate_pending: "Brána merge čeká.",
  open_security_findings: "Otevřený důležitý bezpečnostní nález blokuje merge.",
  self_checks_failed: "Povinná vlastní kontrola agenta selhala.",
  required_checks_failed: "Povinná CI kontrola selhala.",
  stale_against_main: "PR nestojí na aktuální hlavě cílové větve; čeká na aktualizaci.",
  self_checks_missing: "Chybí důkaz vlastních kontrol agenta pro aktuální hlavu.",
  security_review_not_enqueued: "Bezpečnostní review ještě není zařazené.",
  security_review_in_progress: "Běží bezpečnostní review.",
  required_checks_pending: "Povinné CI kontroly ještě nejsou zelené.",
  base_freshness_unobserved: "Neznámo, zda PR stojí na aktuální cílové větvi.",
  template_unobserved: "Popis PR ještě nebyl přečten.",
  template_incomplete: "Popis PR nemá všechny sekce šablony.",
};

export const REVIEW_GATE_VERBS: Record<string, string> = {
  "review.claim": "Převzít review", "review.self_checks": "Doložit vlastní kontroly",
  "pr.update_branch": "Aktualizovat větev PR",
};
