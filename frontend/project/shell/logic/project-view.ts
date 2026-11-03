/** Výstup hlavní lišty Projektu: Architektura projektu (výchozí), Studio (docs/studio.md), Srdce (plátno 1, `heart-canvas/`),
 * Záměr stránky (plátno 2, `intent-canvas/`, s `page=<nodeId>`) nebo Graphify-out; v adrese `projectView`. */
export type ProjectMapKind = "graphify" | "architecture" | "studio" | "heart" | "intent";
export function readProjectView(value: string | null): ProjectMapKind {
  return value === "graphify" || value === "studio" || value === "heart" || value === "intent" ? value : "architecture";
}
