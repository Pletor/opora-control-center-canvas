import { useMemo } from "react";
import type { BinaryFileData, BinaryFiles } from "@excalidraw/excalidraw/types";
import { api } from "@/shared/types/logic/types";
import { drawingFiles, uploadedDrawingFiles } from "@/editor/canvas/drawing/logic/drawing-state";
import { fileIdBatches, filesToUpload, imageFileIds, missingFileIds, type DrawingFile } from "@/editor/canvas/drawing/logic/drawing-files";

type Element = { type: string; isDeleted?: boolean; fileId?: string | null };

// Obrázky kresby pro jeden projekt: načtení k otevřené scéně a nahrání před uložením scény.
export function useDrawingFiles(project: string, workspace: string) {
  return useMemo(() => {
    const uploadedKey = (id: string) => JSON.stringify([project, id]);
    const uploaded = { has: (id: string) => uploadedDrawingFiles.has(uploadedKey(id)) };

    /** Soubory pro `initialData.files`: z mezipaměti, chybějící ze serveru. `failed` = část se nenačetla. */
    async function load(elements: readonly Element[]): Promise<{ files: BinaryFiles; failed: boolean }> {
      const ids = imageFileIds(elements);
      let failed = false;
      for (const batch of fileIdBatches(missingFileIds(ids, drawingFiles))) {
        try {
          const params = new URLSearchParams({ project, workspace, ids: batch.join(",") });
          const value = await api<{ files: DrawingFile[] }>("/api/drawing-files?" + params);
          for (const file of value.files) {
            drawingFiles.set(file.id, file as BinaryFileData);
            uploadedDrawingFiles.add(uploadedKey(file.id));
          }
        } catch {
          failed = true;
        }
      }
      const files: BinaryFiles = {};
      for (const id of ids) {
        const file = drawingFiles.get(id);
        if (file) files[id] = file;
      }
      return { files, failed: failed || ids.some((id) => !drawingFiles.has(id)) };
    }

    /** Zapamatuje si soubory, které editor právě drží (vložený screenshot, přetažený obrázek). */
    function remember(files: BinaryFiles) {
      for (const [id, file] of Object.entries(files)) if (!drawingFiles.has(id)) drawingFiles.set(id, file);
    }

    /** Nahraje každý obrázek scény, který server ještě nemá; chyba přeruší ukládání scény. */
    async function upload(elements: readonly Element[], files: BinaryFiles) {
      remember(files);
      const plan = filesToUpload(imageFileIds(elements), Object.fromEntries(drawingFiles), uploaded);
      if (plan.unsupported.length)
        throw new Error(`Obrázek typu ${plan.unsupported[0].mimeType} nelze uložit; použij PNG, JPEG, WebP nebo GIF.`);
      for (const file of plan.upload) {
        await api("/api/drawing-file", { project, workspace, file: { id: file.id, mimeType: file.mimeType, dataURL: file.dataURL } });
        uploadedDrawingFiles.add(uploadedKey(file.id));
      }
    }

    return { load, remember, upload };
  }, [project, workspace]);
}
