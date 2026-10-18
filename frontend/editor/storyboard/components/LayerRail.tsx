// Svislý pás vrstev vlevo: miniatura každé vrstvy (jen ta vrstva na průhledném), název a přepínač viditelnosti.
// Poslední vrstva „Šipky a poznámky“ zapíná a vypíná overlay anotací. Dílek jen hlásí přepnutí vrstvy.
import { useMemo } from "react";
import type { AnimationDef } from "../logic/animations";
import { ANNOTATION_LAYER, SKETCH_LAYER, layersOf } from "../logic/storyboard-layout";
import type { Annotation, Storyboard } from "../logic/storyboard-model";
import PaintThumb from "./PaintThumb";

const NONE: ReadonlySet<string> = new Set();

export default function LayerRail({ board, animation, thumbT, annotations, sketch, stale, visible, error, onToggle }: {
  board: Storyboard;
  animation: AnimationDef;
  /** Čas vybraného momentu: miniatury ukazují jeho stav, takže se nepřekreslují při přehrávání. */
  thumbT: number;
  annotations: Annotation[];
  /** PNG skici vybraného momentu a příznak, že je neaktuální. */
  sketch?: HTMLImageElement | null;
  stale?: boolean;
  visible: ReadonlySet<string>;
  /** Chyba animace (kód nebo scéna) jako celá věta, např. „Kód animace selhal: …“; ukáže se nad pásem. */
  error?: string;
  onToggle: (id: string) => void;
}) {
  // Množiny vrstev se drží stabilně, aby se miniatury nepřekreslovaly při každém kroku přehrávání.
  const layers = useMemo(() => layersOf(animation).map((layer) => ({ ...layer, only: layer.id === ANNOTATION_LAYER ? NONE : new Set([layer.id]) })), [animation]);
  return (
    <ul className="storyboard__layers" aria-label="Vrstvy">
      {error && <li className="storyboard__layers-error" role="alert">{error}</li>}
      {layers.map((layer) => {
        const on = visible.has(layer.id);
        return (
          <li key={layer.id} className={"storyboard__layer" + (on ? "" : " storyboard__layer--hidden")}>
            <button type="button" className="storyboard__layer-thumb" aria-pressed={on} aria-label={(on ? "Skrýt vrstvu " : "Ukázat vrstvu ") + layer.label} onClick={() => onToggle(layer.id)}>
              <PaintThumb board={board} animation={animation} t={thumbT} w={96} h={54}
                visible={layer.only} annotations={layer.id === ANNOTATION_LAYER ? annotations : undefined} sketch={layer.id === SKETCH_LAYER ? sketch : undefined} />
            </button>
            <label className="storyboard__layer-name">
              <input type="checkbox" checked={on} onChange={() => onToggle(layer.id)} />
              {layer.label}
              {layer.id === SKETCH_LAYER && stale && <span className="storyboard__stale">Náhled neaktuální</span>}
            </label>
          </li>
        );
      })}
    </ul>
  );
}
