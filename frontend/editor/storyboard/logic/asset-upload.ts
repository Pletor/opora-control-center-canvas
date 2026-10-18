// Podklady storyboardu bez Reactu: kontrola nahrávaného souboru, nový podklad s výchozím pokynem a úprava podkladu,
// která vrací `answered` na false, jakmile se změní cokoli, podle čeho agent podklad použil.
import { ASSET_TYPES, MAX_ASSET_BYTES, type StoryboardAsset } from "./storyboard-model";

/** Česká chyba pro soubor, který nejde nahrát jako podklad; `null` = soubor je v pořádku. */
export function checkAssetFile(file: { type: string; size: number; name: string }): string | null {
  if (!(ASSET_TYPES as readonly string[]).includes(file.type)) return "Podklad musí být PNG, JPEG nebo WebP.";
  if (file.size > MAX_ASSET_BYTES) return "Podklad je větší než 10 MB.";
  return null;
}

/** Nový podklad: textura pro celou animaci a všechny momenty, bez barvy a pokynu, čeká na agenta. */
export function newAsset(name: string, fileId: string, mimeType: string): StoryboardAsset {
  return { name, fileId, mimeType, purpose: "texture", target: "", momentId: "", color: "", colorUse: "", note: "", answered: false };
}

/** Pole, jejichž změna znamená nový pokyn pro agenta. Jméno je jen popisek pro člověka. */
const INSTRUCTION_KEYS = ["fileId", "purpose", "target", "momentId", "color", "colorUse", "note"] as const;

/** Vrátí upravený podklad; změna pokynu (obrázek, účel, cíl, moment, barva, pokyn) vrací `answered` na false. */
export function patchAsset(asset: StoryboardAsset, patch: Partial<StoryboardAsset>): StoryboardAsset {
  const next = { ...asset, ...patch };
  const changed = INSTRUCTION_KEYS.some((key) => key in patch && patch[key] !== asset[key]);
  return changed ? { ...next, answered: false } : next;
}
