import { useRef } from "react";
import { createPortal } from "react-dom";
import { useDrawerFocus } from "@/hub/oporahub-card-drawer/logic/use-drawer-focus";
import PlanLensView from "./PlanLensView";
import "../styles/plan-lens.css";

type Props = { project: string; workspace: string; area: string | null; title: string; onClose: () => void };

/**
 * Okno Lens plánu: vyjede zprava přes plátno, ✕ vpravo nahoře a Escape ho zavřou a vrátí fokus tam,
 * odkud se otevřelo. Escape bere jen tehdy, když ho nikdo nezastavil, takže průvodce plátna ho chytí dřív.
 */
export default function PlanLensDialog({ project, workspace, area, title, onClose }: Props) {
  const dialog = useRef<HTMLElement>(null);
  useDrawerFocus(dialog, onClose);
  return createPortal(<div className="plan-lens__overlay" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="plan-lens__dialog" ref={dialog} role="dialog" aria-modal="true" aria-labelledby="plan-lens-title" tabIndex={-1}>
      <header className="plan-lens__dialog-head">
        <h2 id="plan-lens-title" className="plan-lens__dialog-title">{title}</h2>
        <button type="button" className="plan-lens__close" aria-label="Zavřít Lens plánu" onClick={onClose}>✕</button>
      </header>
      <div className="plan-lens__dialog-body"><PlanLensView project={project} workspace={workspace} area={area} /></div>
    </section>
  </div>, document.body);
}
