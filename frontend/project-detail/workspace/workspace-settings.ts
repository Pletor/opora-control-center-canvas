export type WorkspaceMode = "structure" | "drawing" | "map" | "text" | "agents";
export const WORKSPACE_MODES: { key: WorkspaceMode; label: string; hint: string }[] = [
  { key: "structure", label: "Struktura", hint: "Plátno vrstvy: karty, vazby, zanoření." },
  { key: "text", label: "Text", hint: "Dokument a outliner téže vrstvy." },
  { key: "drawing", label: "Kreslení", hint: "Volná kresba a wireframe vrstvy." },
  { key: "map", label: "Mapa", hint: "Celý projekt a vazby napříč vrstvami." },
  { key: "agents", label: "Běhy", hint: "Běhy agentů ze skutečných zdrojů, jen čtení." },
];
export type SurfaceSettings = {
  showGrid: boolean;
  snap: boolean;
  gridSize: number;
  drawingGrid: boolean;
};
export const SETTINGS_KEY = "opora:surface-settings:v1";
export const DEFAULT_SETTINGS: SurfaceSettings = {
  showGrid: true,
  snap: false,
  gridSize: 20,
  drawingGrid: false,
};
export function readSettings(): SurfaceSettings {
  try {
    const value = JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "null");
    if (
      value &&
      typeof value.showGrid === "boolean" &&
      typeof value.snap === "boolean" &&
      [10, 20, 40].includes(value.gridSize) &&
      typeof value.drawingGrid === "boolean"
    )
      return value;
  } catch {
    /* Poškozené preference nejsou projektová data. */
  }
  return { ...DEFAULT_SETTINGS };
}
export function readMode(value: string | null): WorkspaceMode {
  return WORKSPACE_MODES.some((m) => m.key === value) ? (value as WorkspaceMode) : "structure";
}
