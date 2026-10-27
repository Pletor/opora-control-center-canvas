import type { MapCheckTarget } from "../../map-check/logic/map-check";
import type { FlowSummary } from "../logic/studio-flows";

/** Tok domény podle `carries`: sloupec na druh toku (navigace, data, příkaz, událost, neurčeno) s počtem vazeb a seznamem
 * „zdroj → cíl“ seskupeným podle stránky zdroje, barva druhu stejná jako čára na plátně Editoru stránky. Klik na vazbu
 * hlásí cíl rodiči (`onSelect`: stránka, nebo komponenta se svou stránkou); zdroj mimo stránky je jen text. */
export default function StudioFlows({ flows, onSelect }: { flows: FlowSummary[]; onSelect: (target: MapCheckTarget) => void }) {
  const total = flows.reduce((sum, flow) => sum + flow.count, 0);
  return <section className="studio__flows" data-testid="architecture-studio-flows">
    <h3 className="studio__heading">Tok domény <span className="studio__heading-count">{total}</span></h3>
    {!total ? <p className="studio__empty">Mezi prvky domény zatím nevede žádná vazba.</p>
      : <ul className="studio__flow-list">
          {flows.map((flow) => <li key={flow.kind} className={"studio__flow studio__flow--" + flow.kind} data-testid={"architecture-studio-flow-" + flow.kind}>
            <header className="studio__flow-head">
              <span className="studio__flow-swatch" aria-hidden="true"/>
              <span className="studio__flow-label">{flow.label}</span>
              <span className="studio__flow-count">{flow.count}</span>
            </header>
            {flow.groups.map((group) => <div key={group.pageId ?? ""} className="studio__flow-group">
              <span className="studio__flow-page">{group.pageName}</span>
              <ol className="studio__flow-items">
                {group.items.map((item) => <li key={item.edgeId} className="studio__flow-item">
                  {item.target
                    ? <button type="button" className="studio__flow-link" title="Otevřít stránku zdroje a vybrat zdroj" data-testid={"architecture-studio-flow-item-" + item.edgeId}
                        onClick={() => onSelect(item.target!)}>{item.sourceName} → {item.targetName}</button>
                    : <span className="studio__flow-note">{item.sourceName} → {item.targetName}</span>}
                </li>)}
              </ol>
            </div>)}
          </li>)}
        </ul>}
  </section>;
}
