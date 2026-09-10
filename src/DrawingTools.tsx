import { DRAWING_TOOLS, type DrawingTool } from "./drawing-state";
import WireframeTools from "./WireframeTools";
import type { WireframeKind } from "./wireframe-model";

export default function DrawingTools({
  tool,
  ready,
  onTool,
  wireframeMode = false,
  onWireframeMode,
  onInsertWireframe,
}: {
  tool: DrawingTool;
  ready: boolean;
  onTool: (tool: DrawingTool) => void;
  wireframeMode?: boolean;
  onWireframeMode?: (enabled: boolean) => void;
  onInsertWireframe?: (kind: WireframeKind) => void;
}) {
  return (
    <>
      <div className="eyebrow">NÁSTROJE KRESLENÍ</div>
      <div className="drawing-tools">
        {DRAWING_TOOLS.map(([key, label]) => (
          <button
            key={key}
            aria-label={"Nástroj: " + label}
            aria-pressed={tool === key}
            disabled={!ready}
            onClick={() => onTool(key)}
          >
            {label}
          </button>
        ))}
      </div>
      {onWireframeMode && onInsertWireframe && (
        <WireframeTools
          enabled={wireframeMode}
          ready={ready}
          onEnabled={onWireframeMode}
          onInsert={onInsertWireframe}
        />
      )}
      <p className="muted">
        Kresba patří aktuální vrstvě; tvary nejsou uzly projektu. Ukládá se tlačítkem nad plochou. Obrázky, import souborů a webové
        vložky nejsou součástí tohoto řezu.
      </p>
    </>
  );
}
