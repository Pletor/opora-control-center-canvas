export { WORKSPACE_MODES, type WorkspaceMode } from "@/shared/types/logic/workspace-mode";
import { WORKSPACE_MODES, type WorkspaceMode } from "@/shared/types/logic/workspace-mode";
export type SurfaceSettings = {
  showGrid: boolean;
  snap: boolean;
  gridSize: number;
  drawingGrid: boolean;
  /** Starší přepínač odznaků etap; odznak je teď stavový řádek tváře karty, hodnota se jen zachovává. */
  loopBadges: boolean;
};
export const SETTINGS_KEY = "opora:surface-settings:v1";
export const DEFAULT_SETTINGS: SurfaceSettings = {
  showGrid: true,
  snap: false,
  gridSize: 20,
  drawingGrid: false,
  loopBadges: true,
};
export function readSettings(): SurfaceSettings {
  try {
    const value = JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "null");
    if (
      value &&
      typeof value.showGrid === "boolean" &&
      typeof value.snap === "boolean" &&
      [10, 20, 40].includes(value.gridSize) &&
      typeof value.drawingGrid === "boolean" &&
      (value.loopBadges === undefined || typeof value.loopBadges === "boolean")
    )
      return { ...value, loopBadges: value.loopBadges !== false };
  } catch {
    /* Poškozené preference nejsou projektová data. */
  }
  return { ...DEFAULT_SETTINGS };
}
export function readMode(value: string | null): WorkspaceMode {
  return WORKSPACE_MODES.some((m) => m.key === value) ? (value as WorkspaceMode) : "structure";
}
