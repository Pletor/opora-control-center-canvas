// Obrázky skic pro náhledy: stáhne PNG podle `fileId` (`GET /api/drawing-files?ids=`), převede je na `Image` a drží je
// v mezipaměti rodiče podle fileId. Mapa se mění jen při doběhnutí nového obrázku, takže se náhledy překreslí jednou.
import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { DrawingFile } from "@/editor/canvas/drawing/logic/drawing-files";

export type SketchImages = ReadonlyMap<string, HTMLImageElement>;
const EMPTY: SketchImages = new Map();

function load(dataURL: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Skicu se nepodařilo načíst."));
    image.src = dataURL;
  });
}

export function useSketchImages(project: string, workspace: string, fileIds: readonly string[]): SketchImages {
  const cache = useRef(new Map<string, HTMLImageElement>());
  const asked = useRef(new Set<string>());
  const [images, setImages] = useState<SketchImages>(EMPTY);
  const wanted = [...new Set(fileIds)].filter(Boolean).sort().join(",");
  useEffect(() => {
    cache.current = new Map();
    asked.current = new Set();
    setImages(EMPTY);
  }, [project, workspace]);
  useEffect(() => {
    const missing = wanted.split(",").filter((id) => id && !asked.current.has(id));
    if (!missing.length) return;
    missing.forEach((id) => asked.current.add(id));
    (async () => {
      const value = await api<{ files: DrawingFile[] }>("/api/drawing-files?" + new URLSearchParams({ project, workspace, ids: missing.join(",") }));
      for (const file of value.files) {
        try { cache.current.set(file.id, await load(file.dataURL)); } catch { /* chybný obrázek se vynechá */ }
      }
      setImages(new Map(cache.current));
    })().catch(() => { missing.forEach((id) => asked.current.delete(id)); });
  }, [project, workspace, wanted]);
  return images;
}
