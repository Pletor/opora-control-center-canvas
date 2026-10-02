// Dílek STRÁNKY: skupina „Vazby“ — vazby, jejichž zpráva odpovídá hledání (index plátna). Řádek říká
// odkud kam (`fromName → toName`) a pod tím krátce, co se předává. Klik otevře zdrojovou kartu, protože
// vazba patří k té, ze které vychází. Dílek nic nenačítá: shody dostane hotové, klik hlásí nahoru.
import { useState } from "react";
import Icon from "@/ui-kit/icon/components/Icon";
import type { EdgeMatch } from "@/layout/library-navbar/logic/canvas-index";

export default function LibraryEdgeGroup({ edges, onOpen }: { edges: EdgeMatch[]; onOpen: (nodeId: string) => void }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <section className={"library-navbar__group" + (collapsed ? " library-navbar__group--collapsed" : "")}>
      <button
        type="button"
        className="library-navbar__group-head"
        aria-expanded={!collapsed}
        data-testid="library-group-edges"
        onClick={() => setCollapsed((value) => !value)}
      >
        <Icon className={"library-navbar__group-sign" + (collapsed ? "" : " library-navbar__group-sign--open")} name="chevron-right" size={16} />
        <span className="library-navbar__group-label">Vazby</span>
        <small className="library-navbar__group-count">{edges.length}</small>
      </button>
      {!collapsed && (
        <div className="library-navbar__rows">
          {edges.map((edge) => (
            <button
              key={edge.id}
              type="button"
              className="library-navbar__edge"
              title="Otevřít zdrojovou kartu vazby"
              data-testid={"library-edge-" + edge.id}
              onClick={() => onOpen(edge.from)}
            >
              <span className="library-navbar__edge-route">{edge.fromName} → {edge.toName}</span>
              {edge.handoff && <span className="library-navbar__edge-handoff">{edge.handoff}</span>}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
