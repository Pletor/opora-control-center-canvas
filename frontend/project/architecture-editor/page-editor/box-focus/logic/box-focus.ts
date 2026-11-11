// Zanořený pohled boxu plátna 2 (docs/navrhy/2026-11-10-platno-2.md, Verze 5): drobečky od kořenového boxu, adresa
// s otevřeným boxem (`boxId`) a rozložení obrázků inspirace vložených do kresby skici. Bez Reactu, test vedle.
import { imageFileIds } from "@/editor/canvas/drawing/logic/drawing-files";
import type { LayoutSection } from "../../layout-canvas/logic/layout-grid";

/** Cesta od kořenového boxu k otevřenému (drobečky Stránka › Box › vnořený box); neznámý box = prázdná cesta. */
export function focusPath(sections: readonly LayoutSection[], id: string | null): LayoutSection[] {
  const byId = new Map(sections.map((section) => [section.id, section]));
  const path: LayoutSection[] = [];
  for (let current = id ? byId.get(id) : undefined; current && !path.includes(current); current = current.parent ? byId.get(current.parent) : undefined) path.unshift(current);
  return path;
}

/** Dotaz adresy s otevřeným boxem, nebo bez něj (návrat na layout). */
export function withBoxParam(search: string, id: string | null): string {
  const params = new URLSearchParams(search);
  if (id) params.set("boxId", id); else params.delete("boxId");
  return params.toString();
}

/** Obrázky inspirace, které v kresbě ještě nejsou (druhé vložení nic nezdvojí). */
export const notInScene = (files: readonly string[], elements: readonly { type: string; isDeleted?: boolean; fileId?: string | null }[]): string[] => {
  const present = new Set(imageFileIds(elements));
  return files.filter((id) => !present.has(id));
};

type Bounds = { x: number; y: number; width: number; height: number; isDeleted?: boolean };
export const IMAGE_GAP = 40;

/** Kam vložit obrázky: vpravo vedle dosavadní kresby, zarovnané s jejím horním okrajem; prázdná kresba = počátek. */
export function besideScene(elements: readonly Bounds[]): { x: number; y: number } {
  const live = elements.filter((element) => !element.isDeleted);
  if (!live.length) return { x: 0, y: 0 };
  return { x: Math.max(...live.map((element) => element.x + element.width)) + IMAGE_GAP, y: Math.min(...live.map((element) => element.y)) };
}

/** Kostry obrázků pro Excalidraw (`convertToExcalidrawElements`): vedle sebe zleva doprava, delší strana nejvýš `max` px,
 * poměr stran zachovaný, menší obrázek se nezvětšuje. */
export function inspirationSkeletons(images: readonly { fileId: string; width: number; height: number }[], origin: { x: number; y: number }, max = 640) {
  let x = origin.x;
  return images.map(({ fileId, width, height }) => {
    const scale = Math.min(1, max / Math.max(width, height, 1));
    const size = { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
    const skeleton = { type: "image" as const, fileId, x, y: origin.y, ...size, status: "saved" as const };
    x += size.width + IMAGE_GAP;
    return skeleton;
  });
}
