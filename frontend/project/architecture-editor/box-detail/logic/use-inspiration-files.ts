// Náhledy obrázků inspirace: data URL z `/api/drawing-files` (stejné úložiště jako obrázky kresby), po dávkách.
// Nepodporovaný nebo nenačtený soubor náhled nemá; chyba se vrátí jednou větou.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { fileIdBatches, type DrawingFile } from "@/editor/canvas/drawing/logic/drawing-files";
import { safeDrawingPreview } from "@/editor/research/logic/research-model";

export function useInspirationFiles(project: string, workspace: string, ids: readonly string[]): { previews: ReadonlyMap<string, string>; error: string } {
  const [state, setState] = useState<{ previews: ReadonlyMap<string, string>; error: string }>({ previews: new Map(), error: "" });
  const key = ids.join(",");
  useEffect(() => {
    let alive = true;
    if (!ids.length) { setState({ previews: new Map(), error: "" }); return; }
    Promise.all(fileIdBatches([...new Set(ids)]).map((batch) => api<{ files: DrawingFile[] }>("/api/drawing-files?" + new URLSearchParams({ project, workspace, ids: batch.join(",") }))))
      .then((results) => { if (alive) setState({ previews: new Map(results.flatMap((result) => result.files).flatMap((file) => { const src = safeDrawingPreview(file); return src ? [[file.id, src] as const] : []; })), error: "" }); },
        (cause) => { if (alive) setState((previous) => ({ ...previous, error: cause instanceof Error ? cause.message : String(cause) })); });
    return () => { alive = false; };
  }, [project, workspace, key]);
  return state;
}
