// Malý náhled celku v rohu plátna: vždy všechny vrstvy ve stavu času t, i když člověk na plátně některé schoval.
// Klik ho zvětší (420 px) nebo zmenší (240 px); velikost je jen pohled a drží ji sám dílek.
import { useState } from "react";
import type { AnimationDef } from "../logic/animations";
import type { Storyboard } from "../logic/storyboard-model";
import PaintThumb from "./PaintThumb";

export default function MiniPreview({ board, animation, t, visible, sketch }: { board: Storyboard; animation: AnimationDef; t: number; visible: ReadonlySet<string>; sketch?: HTMLImageElement | null }) {
  const [large, setLarge] = useState(false);
  const w = large ? 420 : 240;
  return (
    <button type="button" className={"storyboard__mini" + (large ? " storyboard__mini--large" : "")} aria-label={large ? "Zmenšit náhled celku" : "Zvětšit náhled celku"} onClick={() => setLarge(!large)}>
      <PaintThumb board={board} animation={animation} t={t} visible={visible} sketch={sketch} w={w} h={Math.round((w * 9) / 16)} />
    </button>
  );
}
