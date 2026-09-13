export type WorkspaceMode = "structure" | "drawing" | "map" | "text" | "agents";
export const WORKSPACE_MODES: { key: WorkspaceMode; label: string; hint: string }[] = [
  { key: "structure", label: "Struktura", hint: "Plátno vrstvy: karty, vazby, zanoření." },
  { key: "text", label: "Text", hint: "Dokument a outliner téže vrstvy." },
  { key: "drawing", label: "Kreslení", hint: "Volná kresba a wireframe vrstvy." },
  { key: "map", label: "Mapa", hint: "Celý projekt a vazby napříč vrstvami." },
  { key: "agents", label: "Běhy", hint: "Běhy agentů ze skutečných zdrojů, jen čtení." },
];
