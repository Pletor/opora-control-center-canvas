// Přehled po disciplínách (docs/schranka-neurony.md §6): u každé disciplíny rozsahu malý pruh pokrytí, kolik
// kapitol už pracuje jako karty a průměrná chyba předpovědi ověřených fragmentů. Klik přepne pohled na
// disciplínu (callback rodiči). Jen zobrazení.
import CoverageBar, { chaptersLabel } from "@/editor/node-detail/brief-vault/components/CoverageBar";
import { formatError } from "@/editor/node-detail/brief-vault/logic/gate-bar";
import { disciplineLabel, groupLabel, type DisciplineView } from "../logic/disciplines";
import type { DisciplineStat } from "../logic/discipline-stats";

export default function DisciplineOverview({ stats, view, onView }: { stats: DisciplineStat[]; view: DisciplineView; onView: (view: DisciplineView) => void }) {
  return (
    <section className="vault-panel" aria-label="Po disciplínách" data-testid="vault-discipline-overview">
      <h3 className="vault-panel__title">Po disciplínách</h3>
      {stats.length ? stats.map((item) => (
        <button key={item.id} type="button" className="vault-discipline-row" aria-pressed={item.id === view} onClick={() => onView(item.id)}>
          <span className="vault-discipline-row__name">{groupLabel(item.id) ? `${groupLabel(item.id)} · ` : ""}{disciplineLabel(item.id)}</span>
          <span className="vault-discipline-row__bar"><CoverageBar coverage={item.coverage} legend={false} /></span>
          <span className="vault-discipline-row__num">{item.asCards}/{item.coverage.leaves} {chaptersLabel(item.coverage.leaves)} jako karty</span>
          <span className="vault-discipline-row__num" title="Průměr predikční chyby bran Ověřeno: 0 = předpověď sedí, 1 = úplně vedle">
            chyba předpovědi {formatError(item.meanError)}{item.verified ? ` (${item.verified})` : ""}</span>
        </button>
      )) : <p className="vault-panel__text">Schránka zatím nemá kapitoly v žádné disciplíně.</p>}
    </section>
  );
}
