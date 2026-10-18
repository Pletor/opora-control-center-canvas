// Hromadné posouzení návrhů agenta v Paměti projektu: skupiny podle rozsahu a výběr bez Reactu.
import type { Rule } from "@/shared/desktop-state/logic/types";
import { isAgentRule } from "@/shared/desktop-state/logic/agent-rule";

export type RuleBatchGroup = { key: string; label: string; rules: Rule[] };

const ORDER = { project: 0, path: 1, node: 2 } as const;

function groupLabel(rule: Rule): string {
  if (rule.scope === "project") return "Celý projekt";
  if (rule.scope === "path") return `Cesta ${rule.target}`;
  return `Karta ${rule.target}`;
}

/** Návrhy agenta seskupené podle rozsahu (projekt, cesty, karty) a cíle; pořadí uvnitř skupiny zůstává. */
export function proposalGroups(rules: Rule[]): RuleBatchGroup[] {
  const groups = new Map<string, RuleBatchGroup>();
  for (const rule of rules) {
    if (!isAgentRule(rule)) continue;
    const key = rule.scope === "project" ? "project" : `${rule.scope}:${rule.target}`;
    const group = groups.get(key) ?? { key, label: groupLabel(rule), rules: [] };
    group.rules.push(rule);
    groups.set(key, group);
  }
  return [...groups.values()].sort((a, b) =>
    ORDER[a.rules[0].scope] - ORDER[b.rules[0].scope] || a.label.localeCompare(b.label, "cs"));
}

/** Vybrané návrhy: výchozí jsou zaškrtnuté všechny, člověk jen odznačuje (`excluded`). */
export function selectedProposals(groups: RuleBatchGroup[], excluded: ReadonlySet<string>): Rule[] {
  return groups.flatMap((group) => group.rules.filter((rule) => !excluded.has(rule.id)));
}

/** Zaškrtnutí / odznačení jednoho návrhu nebo celé skupiny (`ids`). */
export function toggled(excluded: ReadonlySet<string>, ids: string[], checked: boolean): Set<string> {
  const next = new Set(excluded);
  for (const id of ids) {
    if (checked) next.delete(id);
    else next.add(id);
  }
  return next;
}
