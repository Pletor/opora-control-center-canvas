// Obrázky kresby bez Reactu: které soubory scéna potřebuje, co chybí a co se smí nahrát nebo vložit.
// Scéna nese jen fileId; data obrázku leží na serveru (`/api/drawing-file(s)`), jednou na projekt.

export const DRAWING_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"] as const;
export const DRAWING_FILES_PER_REQUEST = 200;

export type DrawingFile = { id: string; mimeType: string; dataURL: string; created: number };
type ElementLike = { type: string; isDeleted?: boolean; fileId?: string | null };

export function isDrawingImageType(mimeType: string) {
  return (DRAWING_IMAGE_TYPES as readonly string[]).includes(mimeType);
}

/** Unikátní fileId nesmazaných obrázků v pořadí, jak leží ve scéně. */
export function imageFileIds(elements: readonly ElementLike[]): string[] {
  const ids = new Set<string>();
  for (const element of elements)
    if (element.type === "image" && !element.isDeleted && typeof element.fileId === "string" && element.fileId) ids.add(element.fileId);
  return [...ids];
}

/** ID, která ještě nejsou známá (v mezipaměti ani ve scéně editoru). */
export function missingFileIds(ids: readonly string[], known: { has(id: string): boolean }): string[] {
  return ids.filter((id) => !known.has(id));
}

/** Rozdělí ID do dávek, které server přijme jedním požadavkem. */
export function fileIdBatches(ids: readonly string[], size = DRAWING_FILES_PER_REQUEST): string[][] {
  const batches: string[][] = [];
  for (let start = 0; start < ids.length; start += size) batches.push(ids.slice(start, start + size));
  return batches;
}

/**
 * Co poslat před uložením scény: obrázky, které scéna používá, editor je má a server je ještě nepotvrdil.
 * Nepodporovaný typ (např. SVG) se nenahrává; volající ho ohlásí a scénu neuloží.
 */
export function filesToUpload(
  ids: readonly string[],
  available: Readonly<Record<string, DrawingFile | undefined>>,
  uploaded: { has(id: string): boolean },
): { upload: DrawingFile[]; unsupported: DrawingFile[] } {
  const upload: DrawingFile[] = [];
  const unsupported: DrawingFile[] = [];
  for (const id of ids) {
    const file = available[id];
    if (!file || uploaded.has(id)) continue;
    (isDrawingImageType(file.mimeType) ? upload : unsupported).push(file);
  }
  return { upload, unsupported };
}

/** Přetažení souborů: obrázky povolených typů pustí Excalidraw, cokoli jiného se zablokuje. */
export function dropIsBlocked(files: ArrayLike<{ type: string }>): boolean {
  return Array.from(files).some((file) => !isDrawingImageType(file.type));
}

type PasteLike = {
  files?: Readonly<Record<string, { mimeType: string } | undefined>>;
  mixedContent?: readonly { type: string }[];
  elements?: readonly { type: string }[];
};

/** Vložení ze schránky: obrázky ano, obrázek z URL a webové vložky (embed, iframe, magicframe) ne. */
export function pasteIsAllowed(data: PasteLike): boolean {
  if (Object.values(data.files ?? {}).some((file) => !file || !isDrawingImageType(file.mimeType))) return false;
  if (data.mixedContent?.some((item) => item.type === "imageUrl")) return false;
  return !data.elements?.some((element) => ["embeddable", "iframe", "magicframe"].includes(element.type));
}
