// Miniatura snímku: nakreslí animaci ve stavu času t jen s danými vrstvami (a volitelně šipky momentu) do malého
// canvasu na průhledné pozadí. Překreslí se jen při změně vstupů; čas přehrávání sem rodič nepouští.
// U webové scény je pod canvasem zmenšený týž dokument v iframe (jen když je vidět aspoň jedna vrstva scény);
// canvas nad ním nese skicu a šipky.
import { useEffect, useRef, type CSSProperties } from "react";
import type { AnimationDef } from "../logic/animations";
import { drawAnnotations } from "../logic/annotation-overlay";
import { SKETCH_LAYER } from "../logic/storyboard-layout";
import { stateAt, type Annotation, type Storyboard } from "../logic/storyboard-model";
import { useElementBox } from "../logic/use-element-box";
import SceneFrame from "./SceneFrame";

export default function PaintThumb({ board, animation, t, visible, annotations, sketch, w, h, className }: {
  board: Storyboard;
  animation: AnimationDef;
  t: number;
  visible: ReadonlySet<string>;
  annotations?: Annotation[];
  /** PNG skici momentu; kreslí se přes animaci, jen když je zapnutá vrstva Skica. */
  sketch?: HTMLImageElement | null;
  w: number;
  h: number;
  className?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const scene = animation.scene;
  const box = useElementBox(wrap, !!scene);
  useEffect(() => {
    const ctx = ref.current?.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, w, h);
    animation.paint(ctx, w, h, stateAt(board, animation, t), t, board, visible);
    if (sketch && visible.has(SKETCH_LAYER)) ctx.drawImage(sketch, 0, 0, w, h);
    if (annotations?.length) drawAnnotations(ctx, w, h, annotations, -1);
  }, [board, animation, t, visible, annotations, sketch, w, h]);
  if (!scene) return <canvas ref={ref} className={className} width={w} height={h} aria-hidden="true" />;

  const hidden = animation.layers.filter((l) => !visible.has(l.id)).map((l) => l.id);
  const size = { "--thumb-w": `${w}px`, "--thumb-h": `${h}px` } as CSSProperties;
  return (
    <div ref={wrap} className={"storyboard__thumb" + (className ? " " + className : "")} style={size} aria-hidden="true">
      {hidden.length < animation.layers.length && (
        <SceneFrame html={scene.srcdoc} board={board} t={t} hidden={hidden} assets={scene.assets} w={box?.width ?? w} h={box?.height ?? h} onError={scene.onError} />
      )}
      <canvas ref={ref} className="storyboard__thumb-canvas" width={w} height={h} />
    </div>
  );
}
