import type { Graph } from "@/shared/types/logic/types";
import { environmentAddress } from "./domain-kind";

// Domény, ke kterým jde přiřadit worktree (docs/domeny-a-worktree.md §6): jen sektory
// `site.kind="application"` s právě jedním prostředím. Popisek „Produkce · www.example.cz“,
// pořadí Produkce, Vývoj, ostatní skupiny, uvnitř podle hostu.

export type DomainChoice = { id: string; label: string };

const GROUP_ORDER = ["Produkce", "Vývoj"];
const rank = (group: string) => { const index = GROUP_ORDER.indexOf(group); return index < 0 ? GROUP_ORDER.length : index; };

export function domainChoices(graph: Graph): DomainChoice[] {
  const rows = graph.nodes.flatMap((node) => {
    if (node.site?.kind !== "application" || node.site.environments.length !== 1) return [];
    const env = node.site.environments[0];
    return [{ id: node.id, group: env.name, host: environmentAddress(env) || node.name }];
  });
  rows.sort((a, b) => rank(a.group) - rank(b.group) || a.group.localeCompare(b.group) || a.host.localeCompare(b.host));
  return rows.map((row) => ({ id: row.id, label: `${row.group} · ${row.host}` }));
}

/** Popisek domény pro seznam skladiště; neznámá doména (smazaná, `project`) = její ID. */
export function domainLabel(choices: DomainChoice[], id: string): string {
  return choices.find((choice) => choice.id === id)?.label ?? (id || "bez domény");
}
