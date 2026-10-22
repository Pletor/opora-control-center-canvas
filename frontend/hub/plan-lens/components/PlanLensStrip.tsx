import type { PlanLens } from "../logic/plan-lens-read";
import { graphifyText, statItems } from "../logic/plan-lens-stats";

/** Pruh nad plátnem: šest čísel plánu, stav Graphify, legenda (co je kód, co plán, co vazba z Graphify) a obnova. */
export default function PlanLensStrip({ lens, busy, onReload }: { lens: PlanLens; busy: boolean; onReload: () => void }) {
  return <header className="plan-lens__strip" data-oh-plan-digest={lens.digest} data-oh-plan-area={lens.area ?? ""}>
    <div className="plan-lens__stats" role="list" aria-label="Čísla plánu">
      {statItems(lens.stats).map(item => <span key={item.key} role="listitem" className={`plan-lens__stat${item.value ? "" : " plan-lens__stat--zero"}`}
        title={item.title} data-oh-plan-stat={item.key}>{item.text}</span>)}
      <span className="plan-lens__grow" />
      <span className={`plan-lens__graphify${lens.graphify.available ? "" : " plan-lens__graphify--off"}`} data-oh-plan-graphify={String(lens.graphify.available)}
        title={lens.graphify.sourceRevision ?? undefined}>{graphifyText(lens.graphify)}</span>
      <button type="button" className="plan-lens__reload" disabled={busy} onClick={onReload}>{busy ? "Načítám…" : "Obnovit"}</button>
    </div>
    <ul className="plan-lens__legend" aria-label="Legenda">
      <li className="plan-lens__legend-item"><span className="plan-lens__swatch plan-lens__swatch--code" aria-hidden="true" />plná část = kód existuje</li>
      <li className="plan-lens__legend-item"><span className="plan-lens__badge">plán</span>odznak „plán“ = plánováno, kód zatím není</li>
      <li className="plan-lens__legend-item"><span className="plan-lens__swatch plan-lens__swatch--link" aria-hidden="true" />šedá vazba „kód“ = vazba z Graphify</li>
    </ul>
  </header>;
}
