// Pravidlo, které napsal agent, je jen návrh: agenti ho mezi platnými pravidly nevidí, dokud ho člověk neuloží.
import type { Rule } from "@/shared/desktop-state/logic/types";

export const AGENT_RULE_LABEL = "návrh agenta – čeká na schválení";

export const isAgentRule = (rule: { by?: string }) => rule.by === "agent";

/** Uložení člověkem = schválení: pravidlo ztratí `by`, takže se z návrhu stává platné pravidlo. */
export function asHumanRule(rule: Rule, text = rule.text): Rule {
  const { by: _by, ...rest } = rule;
  return { ...rest, text };
}

/** Rozhodnutí člověka o návrhu agenta: schválit (pravidlo začne platit) nebo zamítnout (odebere se). */
export type RuleReviewDecision = "approve" | "reject";

/** Požadavek posouzení návrhu; `expected` je přečtený návrh, server ho porovná (CAS) a agentovi vrátí 403. */
export function ruleReviewRequest(project: string, workspace: string, rule: Rule, decision: RuleReviewDecision) {
  return { url: "/api/desktop-v3/rule-review", body: { project, workspace, id: rule.id, decision, expected: rule } };
}

/** Strop jedné dávky posouzení; server větší dávku odmítne. */
export const MAX_RULE_REVIEW_BATCH = 500;

/** Hromadné posouzení vybraných návrhů jedním krokem: všechno, nebo nic (CAS každého přečteného návrhu). */
export function ruleReviewBatchRequest(project: string, workspace: string, rules: Rule[], decision: RuleReviewDecision) {
  return {
    url: "/api/desktop-v3/rule-review-batch",
    body: { project, workspace, decision, items: rules.map((rule) => ({ id: rule.id, expected: rule })) },
  };
}
