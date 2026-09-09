import { DRAWING_TOOLS, type DrawingTool } from "./drawing-state";
export default function DrawingTools({
  tool,
  ready,
  onTool,
}: {
  tool: DrawingTool;
  ready: boolean;
  onTool: (tool: DrawingTool) => void;
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
      <p className="muted">
        Kresba patří aktuální vrstvě. Tvary nejsou uzly projektu. Kresbu ukládej
        tlačítkem nad plochou.
      </p>
      <p className="muted">
        Obrázky, import souborů a webové vložky nejsou součástí tohoto řezu.
      </p>
    </>
  );
}
