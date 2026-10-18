// Dílek Struktury: skupina „Vazby“ — vazby, jejichž zpráva odpovídá hledání (index plátna). Řádek říká
// odkud kam (`fromName → toName`) a pod tím krátce, co se předává. Klik otevře zdrojovou kartu, protože
// vazba patří k té, ze které vychází. Dílek nic nenačítá: shody dostane hotové, klik hlásí nahoru.
import { useState } from "react";
import Icon from "@/ui-kit/icon/components/Icon";
import type { EdgeMatch } from "@/layout/structure-panel/logic/canvas-index";

export default function StructureEdgeGroup({ edges, onOpen }: { edges: EdgeMatch[]; onOpen: (nodeId: string) => void }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <section className={"structure-panel__group" + (collapsed ? " structure-panel__group--collapsed" : "")}>
      <button
        type="button"
        className="structure-panel__group-head"
        aria-expanded={!collapsed}
        data-testid="structure-group-edges"
        onClick={() => setCollapsed((value) => !value)}
      >
        <Icon className={"structure-panel__group-sign" + (collapsed ? "" : " structure-panel__group-sign--open")} name="chevron-right" size={16} />
        <span className="structure-panel__group-label">Vazby</span>
        <small className="structure-panel__group-count">{edges.length}</small>
      </button>
      {!collapsed && (
        <div className="structure-panel__rows">
          {edges.map((edge) => (
            <button
              key={edge.id}
              type="button"
              className="structure-panel__edge"
              title="Otevřít zdrojovou kartu vazby"
              data-testid={"structure-edge-" + edge.id}
              onClick={() => onOpen(edge.from)}
            >
              <span className="structure-panel__edge-route">{edge.fromName} → {edge.toName}</span>
              {edge.handoff && <span className="structure-panel__edge-handoff">{edge.handoff}</span>}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
