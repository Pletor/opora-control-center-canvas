// Jeden pojmenovaný celek plochy Agenti: rám s titulkem, jednou větou „k čemu to je / kdo sem píše“
// a přepínačem rozbalení. Dílek nic nenačítá a o obsahu nic neví — dostane ho v `children`. Kotva
// (`id`) nese ID karty, takže na ni umí odkázat přehled i zpráva na vazbě. Tělo se při sbalení
// neodmontuje, jen skryje: rozepsaná zpráva ani otevřené vlákno komunikace tím nezmizí.
import type { ReactNode } from "react";
import { segmentId, type SegmentDef } from "@/editor/node-detail/agent-workspace/segments/logic/agent-segments";
import "@/editor/node-detail/agent-workspace/segments/styles/agent-segments.css";

export default function AgentSegment({
  nodeId,
  segment,
  open,
  onToggle,
  collapsible = true,
  children,
}: {
  nodeId: string;
  segment: SegmentDef;
  open: boolean;
  /** Rodič (deska) drží rozbalení pro celou aplikaci; dílek jen hlásí, co uživatel zmáčkl. */
  onToggle: (open: boolean) => void;
  /** Přehled se nesbaluje: bez něj by plocha ztratila jediné místo, odkud se člověk orientuje. */
  collapsible?: boolean;
  children: ReactNode;
}) {
  const id = segmentId(nodeId, segment.id);
  const shown = collapsible ? open : true;
  return (
    <section
      id={id}
      className={
        `agent-segments__segment agent-segments__segment--${segment.area}` +
        (segment.wide ? " agent-segments__segment--wide" : "") +
        (shown ? " agent-segments__segment--open" : "")
      }
      aria-label={segment.title}
      data-testid={`agent-segment-${segment.id}`}
    >
      <header className="agent-segments__segment-head">
        <h3 className="agent-segments__segment-title">{segment.title}</h3>
        {collapsible && (
          <button
            type="button"
            className="nodrag agent-segments__toggle"
            aria-expanded={shown}
            aria-controls={`${id}-body`}
            onClick={() => onToggle(!shown)}
          >
            {shown ? "Sbalit" : "Rozbalit"}
          </button>
        )}
      </header>
      <p className="agent-segments__caption">{segment.caption}</p>
      <div className="agent-segments__segment-body" id={`${id}-body`} hidden={!shown}>
        {children}
      </div>
    </section>
  );
}
