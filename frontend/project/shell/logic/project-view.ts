/** Výstup hlavní lišty Projektu: Architektura projektu (výchozí), Studio (docs/studio.md) nebo Záměr stránky (plátno 2,
 * `intent-canvas/`, s `page=<nodeId>`); v adrese `projectView`. Srdce (plátno 1) sem nepatří: má vlastní obrazovku
 * `screen=heart`. Staré odkazy `heart`, `graphify` a neznámé hodnoty vedou do architektury. */
export type ProjectMapKind = "architecture" | "studio" | "intent";
export function readProjectView(value: string | null): ProjectMapKind {
  return value === "studio" || value === "intent" ? value : "architecture";
}
