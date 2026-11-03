/** Výstup hlavní lišty Projektu: Architektura projektu (výchozí), Studio (docs/studio.md), Záměr stránky (plátno 2,
 * `intent-canvas/`, s `page=<nodeId>`) nebo Správa webu (`site-admin/`); v adrese `projectView`. Srdce (plátno 1) sem nepatří: má vlastní obrazovku
 * `screen=heart`. Staré odkazy `heart`, `graphify` a neznámé hodnoty vedou do architektury. */
export type ProjectMapKind = "architecture" | "studio" | "intent" | "site";
export function readProjectView(value: string | null): ProjectMapKind {
  return value === "studio" || value === "intent" || value === "site" ? value : "architecture";
}
