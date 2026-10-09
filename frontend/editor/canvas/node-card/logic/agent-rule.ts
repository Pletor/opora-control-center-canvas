// Pravidlo, které napsal agent, je jen návrh: agenti ho mezi platnými pravidly nevidí, dokud ho člověk neuloží.
import type { Rule } from "@/shared/desktop-state/logic/types";

export const AGENT_RULE_LABEL = "návrh agenta – čeká na schválení";

export const isAgentRule = (rule: { by?: string }) => rule.by === "agent";

/** Uložení člověkem = schválení: pravidlo ztratí `by`, takže se z návrhu stává platné pravidlo. */
export function asHumanRule(rule: Rule, text = rule.text): Rule {
  const { by: _by, ...rest } = rule;
  return { ...rest, text };
}
