// Plátno storyboardu: vykreslí jen viditelné vrstvy animace v čase t a přes ně (je-li vrstva zapnutá) šipky a poznámky momentu.
// Dílek nic neukládá; klik a tažení jen hlásí nahoru (poloha, nová anotace, výběr, smazání).
// U webové scény leží pod průhledným plátnem iframe se scénou přesně v ploše plátna; kliky dál bere plátno.
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { drawAnnotations, hitAnnotation } from "../logic/annotation-overlay";
import type { AnimationDef } from "../logic/animations";
import { ANNOTATION_LAYER, SKETCH_LAYER, paintLayers } from "../logic/storyboard-layout";
import { stateAt, type Annotation, type Point, type Storyboard } from "../logic/storyboard-model";
import { useElementBox } from "../logic/use-element-box";
import SceneFrame from "./SceneFrame";
import "../styles/storyboard.css";

export type StageTool = "place" | "arrow" | "note" | "select";
export const TOOLS: { key: StageTool; label: string }[] = [
  { key: "select", label: "Vybrat" }, { key: "place", label: "Umístit" }, { key: "arrow", label: "Šipka" }, { key: "note", label: "Poznámka" },
];

export default function StoryboardStage({ board, animation, t, visible, annotations, sketch, selectedAnnotation, tool, readOnly, onPlace, onAnnotationAdd, onAnnotationSelect, onAnnotationRemove }: {
  board: Storyboard;
  animation: AnimationDef;
  t: number;
  /** Zapnuté vrstvy včetně vrstvy anotací; schované se nekreslí. */
  visible: ReadonlySet<string>;
  /** Anotace vybraného momentu; vrstva se kreslí přes snímek. */
  annotations: Annotation[];
  /** PNG skici vybraného momentu (z mezipaměti rodiče); kreslí se přes animaci pod šipkami. */
  sketch?: HTMLImageElement | null;
  selectedAnnotation: number;
  tool: StageTool;
  readOnly: boolean;
  onPlace: (x: number, y: number) => void;
  onAnnotationAdd: (annotation: Annotation) => void;
  onAnnotationSelect: (index: number) => void;
  onAnnotationRemove: (index: number) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [drag, setDrag] = useState<{ from: Point; to: Point } | null>(null);
  const { w, h } = board.size;
  const showAnnotations = visible.has(ANNOTATION_LAYER);
  const scene = animation.scene;
  const box = useElementBox(ref, !!scene);
  useEffect(() => {
    const ctx = ref.current?.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, w, h);
    animation.paint(ctx, w, h, stateAt(board, animation, t), t, board, paintLayers(visible));
    if (sketch && visible.has(SKETCH_LAYER)) ctx.drawImage(sketch, 0, 0, w, h);
    if (showAnnotations) drawAnnotations(ctx, w, h, annotations, selectedAnnotation, drag ?? undefined);
  }, [board, animation, t, visible, showAnnotations, annotations, sketch, selectedAnnotation, drag, w, h]);

  function point(event: PointerEvent<HTMLCanvasElement>): Point {
    const box = event.currentTarget.getBoundingClientRect();
    const clamp = (v: number) => Math.min(1, Math.max(0, v));
    return { x: clamp((event.clientX - box.left) / box.width), y: clamp((event.clientY - box.top) / box.height) };
  }
  function down(event: PointerEvent<HTMLCanvasElement>) {
    const p = point(event);
    if (!showAnnotations && tool !== "place") return;
    if (tool === "select") return onAnnotationSelect(hitAnnotation(annotations, p, w / h));
    if (readOnly) return;
    if (tool === "place") onPlace(p.x, p.y);
    else if (tool === "note") onAnnotationAdd({ kind: "note", at: p, text: "" });
    else { event.currentTarget.setPointerCapture(event.pointerId); setDrag({ from: p, to: p }); }
  }
  function move(event: PointerEvent<HTMLCanvasElement>) {
    if (drag) setDrag({ from: drag.from, to: point(event) });
  }
  function up(event: PointerEvent<HTMLCanvasElement>) {
    if (!drag) return;
    const to = point(event);
    setDrag(null);
    if (Math.hypot((to.x - drag.from.x) * (w / h), to.y - drag.from.y) > 0.02) onAnnotationAdd({ kind: "arrow", from: drag.from, to, text: "" });
  }
  function key(event: KeyboardEvent<HTMLCanvasElement>) {
    if (event.key === "Delete" && !readOnly && selectedAnnotation >= 0) onAnnotationRemove(selectedAnnotation);
  }
  const canvas = (
    <canvas ref={ref} className={"storyboard__stage storyboard__stage--" + tool + (scene ? " storyboard__stage--scene" : "")} width={w} height={h} style={{ aspectRatio: `${w} / ${h}` }}
      tabIndex={0} aria-label="Snímek storyboardu" onPointerDown={down} onPointerMove={move} onPointerUp={up} onKeyDown={key} />
  );
  if (!scene) return canvas;
  const hidden = animation.layers.filter((l) => !visible.has(l.id)).map((l) => l.id);
  return (
    <>
      {box && box.width > 0 && (
        <div className="storyboard__stage-scene" style={{ left: box.left, top: box.top }}>
          <SceneFrame html={scene.srcdoc} board={board} t={t} hidden={hidden} assets={scene.assets} w={box.width} h={box.height} onError={scene.onError} />
        </div>
      )}
      {canvas}
    </>
  );
}
