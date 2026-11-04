// Skupiny assetů design systému (`design.assetGroups`, backend `design_system._asset_groups` a `store.put_asset`).
// Soubor patří skupině cestou `assets/<skupina>/<soubor>`, proto skupinu se soubory nejde přejmenovat. Odebrání
// souboru nebo skupiny mění jen dokument; soubor na disku zůstane (backend README „Komponenty a assety“).
import type { AssetFile, AssetGroup } from "@/project/site-admin/logic/site-document";

// Stejné jako `GROUP` a `FILE` / `ASSET_TYPES` v `backend/project/site_admin/`.
const GROUP = /^[A-Za-z0-9][A-Za-z0-9 _.-]{0,62}[A-Za-z0-9_-]$|^[A-Za-z0-9]$/;
const FILE = /^[A-Za-z0-9][A-Za-z0-9 _.-]{0,126}[A-Za-z0-9_-]\.[A-Za-z0-9]{2,5}$|^[A-Za-z0-9]\.[A-Za-z0-9]{2,5}$/;
export const ASSET_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "webp", "svg", "mp4", "webm", "pdf"];
const MAX_BYTES = 10 * 1024 * 1024, MAX_SVG = 2 * 1024 * 1024;

/** Volné jméno nové skupiny: „New set“, „New set 2“… */
export function newGroupName(groups: readonly AssetGroup[]): string {
  const taken = new Set(groups.map((group) => group.name));
  if (!taken.has("New set")) return "New set";
  for (let index = 2; ; index++) if (!taken.has(`New set ${index}`)) return `New set ${index}`;
}

/** Proč jméno skupiny neprojde, nebo `""`. */
export function groupNameProblem(name: string, groups: readonly AssetGroup[], own = ""): string {
  if (!GROUP.test(name)) return "Jméno skupiny: písmena, číslice, mezera, _ . - (bez mezery a tečky na konci).";
  if (name !== own && groups.some((group) => group.name === name)) return `Skupina ${name} už existuje.`;
  return "";
}

/** Proč soubor server nepřijme, nebo `""` (obsah ověří server podle prvních bajtů). */
export function fileProblem(file: { name: string; size: number }): string {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!FILE.test(file.name) || !ASSET_EXTENSIONS.includes(extension)) return `${file.name}: jméno nebo typ (${ASSET_EXTENSIONS.join(", ")}) neprojde.`;
  if (!file.size || file.size > (extension === "svg" ? MAX_SVG : MAX_BYTES)) return `${file.name}: prázdný nebo větší než ${extension === "svg" ? "2" : "10"} MB.`;
  return "";
}

/** Nahraný záznam do skupiny (chybějící skupina vznikne); stejné jméno přepíše (server soubor také přepsal). */
export function withFile(groups: readonly AssetGroup[], group: string, file: AssetFile): AssetGroup[] {
  const all = groups.some((item) => item.name === group) ? groups : [...groups, { name: group, readme: "", files: [] }];
  return all.map((item) => item.name !== group ? item
    : { ...item, files: [...item.files.filter((one) => one.name !== file.name), file] });
}

export const withoutFile = (groups: readonly AssetGroup[], group: string, name: string): AssetGroup[] =>
  groups.map((item) => item.name !== group ? item : { ...item, files: item.files.filter((one) => one.name !== name) });

/** Přejmenování jde jen u prázdné skupiny (soubory mají skupinu v cestě). */
export function renameGroup(groups: readonly AssetGroup[], from: string, to: string): AssetGroup[] {
  return groups.map((item) => item.name === from && !item.files.length ? { ...item, name: to } : item);
}

export const isImage = (file: AssetFile) => file.type.startsWith("image/");

export function fileSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} kB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
