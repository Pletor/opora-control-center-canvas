// Náhled skici boxu: načte uloženou kresbu vrstvy `box/<pageId>/<sectionId>` a vyrenderuje ji do SVG. Excalidraw se
// načte až tehdy, když kresba nějaké prvky má, aby Detail boxu bez skici zůstal lehký. `version` = obnovit po uložení.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { DrawingSnapshot } from "@/editor/canvas/drawing/logic/drawing-state";
import { useDrawingFiles } from "@/editor/canvas/drawing/logic/use-drawing-files";

export type SketchPreview = { loading: boolean; src: string | null; error: string };

export function useSketchPreview(project: string, workspace: string, layer: string, version: number): SketchPreview {
  const images = useDrawingFiles(project, workspace);
  const [preview, setPreview] = useState<SketchPreview>({ loading: true, src: null, error: "" });
  useEffect(() => {
    let alive = true;
    setPreview({ loading: true, src: null, error: "" });
    (async () => {
      const snapshot = await api<DrawingSnapshot>("/api/drawing?" + new URLSearchParams({ project, workspace, layer }));
      const elements = (snapshot.scene?.elements ?? []).filter((element) => !element.isDeleted);
      if (!elements.length) return null;
      const [{ exportToSvg }, { files }] = await Promise.all([import("@excalidraw/excalidraw"), images.load(elements)]);
      const svg = await exportToSvg({ elements, files, appState: { exportBackground: true, viewBackgroundColor: "#ffffff" }, exportPadding: 8 });
      return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg.outerHTML);
    })().then((src) => { if (alive) setPreview({ loading: false, src, error: "" }); },
      (cause) => { if (alive) setPreview({ loading: false, src: null, error: cause instanceof Error ? cause.message : String(cause) }); });
    return () => { alive = false; };
  }, [project, workspace, layer, version, images]);
  return preview;
}
