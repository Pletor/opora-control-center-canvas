import type { ExcalidrawElement } from "@excalidraw/excalidraw/element/types";
import type { BinaryFileData } from "@excalidraw/excalidraw/types";
export type DrawingScene = { elements: readonly ExcalidrawElement[] };
export type DrawingSnapshot = {
  scene: DrawingScene;
  revision: number;
  readOnly: boolean;
  available: boolean;
  saved_at: string | null;
  source: string;
};
export type DrawingDraft = {
  scene: DrawingScene;
  revision: number;
  savedSignature: string;
};
export const drawingDrafts = new Map<string, DrawingDraft>();
export const drawingSaves = new Map<string, Promise<DrawingSnapshot>>();
// Obrázky kresby přežijí přepnutí vrstvy i s neuloženým draftem: fileId → data (ID je odvozené z obsahu).
export const drawingFiles = new Map<string, BinaryFileData>();
// Co server už potvrdil, klíč `JSON [projekt, fileId]`; to se před uložením scény znovu neposílá.
export const uploadedDrawingFiles = new Set<string>();
export const DRAWING_TOOLS = [
  ["selection", "Výběr"],
  ["hand", "Posun"],
  ["freedraw", "Tužka"],
  ["rectangle", "Obdélník"],
  ["ellipse", "Elipsa"],
  ["diamond", "Kosočtverec"],
  ["line", "Čára"],
  ["arrow", "Šipka"],
  ["text", "Text"],
  ["frame", "Rámec"],
  ["image", "Obrázek"],
  ["eraser", "Guma"],
] as const;
export type DrawingTool = (typeof DRAWING_TOOLS)[number][0];
export function isDrawingTool(value: string): value is DrawingTool {
  return DRAWING_TOOLS.some(([t]) => t === value);
}
export function sceneSignature(scene: DrawingScene) {
  return JSON.stringify(scene);
}
export function discardDrawingDrafts(
  project: string,
  workspace?: string,
  layers?: string[],
) {
  for (const key of drawingDrafts.keys()) {
    const [p, w, layer] = JSON.parse(key) as string[];
    if (
      p === project &&
      (workspace === undefined || w === workspace) &&
      (layers === undefined || layers.includes(layer))
    )
      drawingDrafts.delete(key);
  }
}
