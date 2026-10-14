import type { Rule } from "@/shared/desktop-state/logic/types";
import { AGENT_RULE_LABEL, isAgentRule, type RuleReviewDecision } from "@/shared/desktop-state/logic/agent-rule";

/**
 * Posouzení návrhu pravidla od agenta: štítek a tlačítka Schválit / Zamítnout. Stejný dílek drží
 * pravidla na kartě i v Paměti projektu (projekt, cesta); u pravidla člověka se nevykreslí nic.
 * Bez vlastního stavu: zaneprázdnění a chybu drží rodič, který zápis provádí.
 */
export default function RuleReview({ rule, disabled, review }: {
  rule: Rule; disabled: boolean; review: (rule: Rule, decision: RuleReviewDecision) => void;
}) {
  if (!isAgentRule(rule)) return null;
  return <>
    <small style={{ display: "block" }}>🤖 {AGENT_RULE_LABEL}</small>
    <button type="button" disabled={disabled} title="Uložit pravidlo jako člověk; pak platí i pro agenty"
      onClick={() => review(rule, "approve")}>✓ Schválit</button>
    <button type="button" disabled={disabled} title="Odebrat návrh agenta; mezi pravidla se nedostane"
      onClick={() => review(rule, "reject")}>✗ Zamítnout</button>
  </>;
}
