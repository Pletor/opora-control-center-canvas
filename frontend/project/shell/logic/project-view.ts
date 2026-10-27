/** Výstup hlavní lišty Projektu: Architektura projektu (výchozí), Studio (docs/studio.md) nebo Graphify-out; v adrese `projectView`. */
export type ProjectMapKind = "graphify" | "architecture" | "studio";
export function readProjectView(value: string | null): ProjectMapKind {
  return value === "graphify" || value === "studio" ? value : "architecture";
}
