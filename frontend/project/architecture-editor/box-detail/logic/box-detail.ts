// Detail boxu plátna 2 (docs/navrhy/2026-11-10-platno-2.md, Verze 3): stavy boxu, úprava jedné sekce, inspirace
// (nejvýš 6 obrázků, odkaz, poznámka) a vrstva skici. Bez Reactu, test vedle.
import type { PageSection, SectionInspiration, SectionStatus } from "@/shared/types/logic/types";
import { isDrawingImageType } from "@/editor/canvas/drawing/logic/drawing-files";

export const STATUS_LABELS: Record<SectionStatus, string> = { draft: "Rozpracováno", proposed: "Návrh", approved: "Schváleno" };
export const INSPIRATION_MAX_FILES = 6;
export const INSPIRATION_MAX_BYTES = 10 * 1024 * 1024;
export const INSPIRATION_NOTE_MAX = 200;
/** Funkčnost boxu (`intent`): backend `SECTION_INTENT_MAX` (Verze 6). */
export const INTENT_MAX = 600;

/** Chybějící stav = Rozpracováno. */
export const statusOf = (section: Pick<PageSection, "status">): SectionStatus => section.status ?? "draft";

/** Vrstva kresby skici boxu (`/api/drawing`). */
export const boxSketchLayer = (pageId: string, sectionId: string) => `box/${pageId}/${sectionId}`;

/** Změna jedné sekce v seznamu; id se nepřepíše. Beze změny vrací týž seznam. */
export function patchSection<T extends PageSection>(sections: T[], id: string, patch: Partial<Omit<PageSection, "id">>): T[] {
  const current = sections.find((section) => section.id === id);
  if (!current || Object.entries(patch).every(([key, value]) => JSON.stringify(current[key as keyof PageSection]) === JSON.stringify(value))) return sections;
  return sections.map((section) => (section.id === id ? { ...section, ...patch, id } : section));
}

/** Inspirace a skica jsou obsah (zámek obsahu, na mainu jen ke čtení); název, role, záměr a stav jsou struktura. */
export const patchLock = (patch: Partial<PageSection>): "content" | "structure" => ("inspiration" in patch ? "content" : "structure");

/** Proč obrázek nejde přidat; `null` = jde. `count` = kolik obrázků box už má. */
export function inspirationRejects(file: { type: string; size: number }, count: number): string | null {
  if (count >= INSPIRATION_MAX_FILES) return `Box má nejvýš ${INSPIRATION_MAX_FILES} obrázků inspirace.`;
  if (!isDrawingImageType(file.type)) return "Inspirace přijme jen PNG, JPEG, WebP nebo GIF.";
  if (file.size > INSPIRATION_MAX_BYTES) return "Obrázek je větší než 10 MB.";
  return null;
}

/** Přidá nahrané obrázky bez duplicit, nejvýš do limitu. */
export function addInspirationFiles(inspiration: SectionInspiration | undefined, ids: readonly string[]): SectionInspiration {
  const files = [...new Set([...(inspiration?.files ?? []), ...ids])].slice(0, INSPIRATION_MAX_FILES);
  return { ...inspiration, files };
}

export function removeInspirationFile(inspiration: SectionInspiration | undefined, id: string): SectionInspiration {
  return { ...inspiration, files: (inspiration?.files ?? []).filter((file) => file !== id) };
}

/** Odkaz na web smí být prázdný, jinak jen http(s). */
export function inspirationUrlError(url: string): string | null {
  const value = url.trim();
  if (!value) return null;
  try { const parsed = new URL(value); return parsed.protocol === "https:" || parsed.protocol === "http:" ? null : "Odkaz musí začínat https://."; }
  catch { return "Odkaz není platná adresa webu."; }
}
