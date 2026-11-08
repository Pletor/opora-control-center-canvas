export type WorkspaceMode = "structure" | "drawing" | "map" | "office" | "storyboard" | "text" | "research";
export const WORKSPACE_MODES: { key: WorkspaceMode; label: string; hint: string }[] = [
  { key: "structure", label: "Struktura", hint: "Plátno vrstvy: karty, vazby, zanoření." },
  { key: "map", label: "Velín", hint: "Celá pyramida projektu se stavem procesu a frontou „Čeká na tebe“." },
  { key: "research", label: "Rešerše", hint: "Zjištění, důkazy a významová cesta k řešení." },
  { key: "text", label: "Text", hint: "Dokument a outliner téže vrstvy." },
  { key: "drawing", label: "Kreslení", hint: "Volná kresba a wireframe vrstvy." },
  { key: "office", label: "Kancelář", hint: "Místnosti, stoly a kdo u nich pracuje" },
  { key: "storyboard", label: "Storyboard", hint: "Momenty animace, komentáře a šipky pro agenta." },
];
