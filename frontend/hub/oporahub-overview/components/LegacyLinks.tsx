import type { DetailTarget } from "../logic/overview";

/** Původní drawery a formuláře zůstávají dosažitelné: každá položka otevře stávající detail beze změny.
 *  Lens plánu tu není: má výrazné tlačítko v hlavičce přehledu (`PLAN_LENS_TARGET`). */
export const LEGACY_LINKS: DetailTarget[] = [
  { kind: "changes", title: "Upravit zadání karty" },
  { kind: "graph", title: "Návrhy grafu" },
  { kind: "content", title: "Změny obsahu" },
  { kind: "acceptance", title: "Přijímání návrhů" },
  { kind: "acceptance-policy", title: "Pravidla přijetí plánů" },
  { kind: "executions", title: "Běhy, výsledky a zrušení" },
  { kind: "budgets", title: "Limity běhů" },
  { kind: "process", title: "Proces Control Center" },
  { kind: "evidence", title: "Důkazy z GitHubu" },
  { kind: "tracking", title: "Sledování GitHubu" },
  { kind: "policy", title: "Pravidla review" },
  { kind: "formal", title: "Formální podklady" },
  { kind: "conflicts", title: "Konflikty auto-rebase" },
  { kind: "review-metrics", title: "Metriky review" },
  { kind: "proof-ledger", title: "Kniha důkazů" },
  { kind: "identity", title: "Lidé v review (jen člověk)" },
  { kind: "api", title: "Rozhraní pro agenty" },
  { kind: "history", title: "Starší historie a původní formuláře" },
];

export default function LegacyLinks({ open, onRefresh }: { open: (target: DetailTarget) => void; onRefresh: () => void }) {
  return <footer className="oporahub-overview__footer" aria-label="Podrobné formuláře">
    {LEGACY_LINKS.map(target => <button type="button" key={target.kind} data-oh-detail={target.kind} onClick={() => open(target)}>{target.title}</button>)}
    <button type="button" onClick={onRefresh}>Obnovit podklady</button>
  </footer>;
}
