import type { WireframeKind } from "@/project-detail/inspector/wireframe-model";
import { WIREFRAME_KINDS, getWireframeTemplate } from "@/project-detail/inspector/wireframe-model";

export default function WireframeTools({
  enabled,
  ready,
  onEnabled,
  onInsert,
}: {
  enabled: boolean;
  ready: boolean;
  onEnabled: (enabled: boolean) => void;
  onInsert: (kind: WireframeKind) => void;
}) {
  const blocks = WIREFRAME_KINDS.filter(
    (kind) => getWireframeTemplate(kind).role === "block",
  );
  const elements = WIREFRAME_KINDS.filter(
    (kind) => getWireframeTemplate(kind).role === "element",
  );
  const buttons = (items: readonly WireframeKind[]) =>
    items.map((kind) => {
      const template = getWireframeTemplate(kind);
      return (
        <button
          key={kind}
          type="button"
          disabled={!enabled || !ready}
          onClick={() => onInsert(kind)}
        >
          {template.label}
        </button>
      );
    });
  return (
    <section className="wireframe-tools" aria-label="Wireframe">
      <label className="wireframe-mode">
        <input
          type="checkbox"
          checked={enabled}
          disabled={!ready}
          onChange={(event) => onEnabled(event.target.checked)}
        />
        Wireframe
      </label>
      <p className="muted">Vkládá sémantické rámy a prvky do stejné kresby.</p>
      <h3>Bloky</h3>
      <div className="wireframe-tool-grid">{buttons(blocks)}</div>
      <h3>Prvky</h3>
      <div className="wireframe-tool-grid">{buttons(elements)}</div>
    </section>
  );
}
