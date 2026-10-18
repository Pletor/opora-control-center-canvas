// Pás momentů nahoře: každý moment je záložka s miniaturou snímku, časem a názvem. Vybraná svítí.
// Dílek jen hlásí výběr a přidání momentu v čase t; moment se tahem nepřesouvá (čas se mění ve formuláři).
import type { AnimationDef } from "../logic/animations";
import { needsAgent, type Storyboard } from "../logic/storyboard-model";
import type { SketchImages } from "../logic/use-sketch-images";
import PaintThumb from "./PaintThumb";

export default function MomentStrip({ board, animation, paintVisible, sketches, selected, readOnly, onSelect, onAdd }: {
  board: Storyboard;
  animation: AnimationDef;
  /** Vrstvy animace, které se kreslí do miniatur; v miniaturách jsou vždy všechny. */
  paintVisible: ReadonlySet<string>;
  /** PNG skic podle fileId; miniatura momentu skicu obsahuje. */
  sketches: SketchImages;
  selected: number;
  readOnly: boolean;
  onSelect: (index: number) => void;
  onAdd: () => void;
}) {
  return (
    <div className="storyboard__strip" role="tablist" aria-label="Momenty">
      {board.moments.map((m, i) => (
        <button key={i} type="button" role="tab" aria-selected={i === selected} title={`${m.t} s · ${m.title}`}
          className={"storyboard__strip-item" + (i === selected ? " storyboard__strip-item--selected" : "")} onClick={() => onSelect(i)}>
          <PaintThumb className="storyboard__strip-thumb" board={board} animation={animation} t={m.t} visible={paintVisible} annotations={m.annotations} sketch={m.sketch ? sketches.get(m.sketch.fileId) : undefined} w={160} h={90} />
          <span className="storyboard__strip-time">{m.t.toFixed(1)} s</span>
          <span className="storyboard__strip-title">{m.title || "bez názvu"}</span>
          {needsAgent(m) && <span className="storyboard__new-comment">čeká na agenta</span>}
          {m.sketch?.imageStale && <span className="storyboard__stale">Náhled neaktuální</span>}
        </button>
      ))}
      <button type="button" className="storyboard__strip-add" disabled={readOnly} onClick={onAdd} aria-label="Přidat moment v aktuálním čase" title="Přidat moment v aktuálním čase">+</button>
    </div>
  );
}
