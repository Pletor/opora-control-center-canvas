import { MODELS, SCOPES, type AssistantModel, type AssistantScope } from "./assistant-api";

/**
 * Preference asistenta jsou volba aplikace, ne projektu: jeden klíč pro všechny projekty.
 * Drží výchozí model nové session, velikost panelu (minimalizovat, vpravo, celá plocha)
 * a rozsah práce asistenta (Celý obraz / Výběr, docs/asistent.md §6.1).
 */
export const ASSISTANT_PREFS_KEY = "opora:assistant:v1";

export type PanelSize = "minimized" | "side" | "full";
export const SIZES: PanelSize[] = ["minimized", "side", "full"];

export type AssistantPrefs = { model: AssistantModel; size: PanelSize; scope: AssistantScope };
export const DEFAULT_PREFS: AssistantPrefs = { model: "opus", size: "side", scope: "board" };

/** Uložený JSON → platné preference; neznámé nebo poškozené hodnoty dostanou výchozí. */
export function parsePrefs(raw: string | null): AssistantPrefs {
  try {
    const value = JSON.parse(raw ?? "null");
    if (value && typeof value === "object") {
      return {
        model: MODELS.includes(value.model) ? value.model : DEFAULT_PREFS.model,
        size: SIZES.includes(value.size) ? value.size : DEFAULT_PREFS.size,
        scope: SCOPES.includes(value.scope) ? value.scope : DEFAULT_PREFS.scope,
      };
    }
  } catch {
    /* Poškozené preference nejsou data projektu. */
  }
  return { ...DEFAULT_PREFS };
}

/** Esc zmenší panel o jeden stupeň: celá plocha → vpravo → lišta. Lišta už zůstane. */
export function smallerSize(size: PanelSize): PanelSize {
  return size === "full" ? "side" : "minimized";
}

/** Tlačítko Asistent otevře poslední velikost; z lišty se otevírá vpravo, aby bylo co číst. */
export function reopenSize(last: PanelSize): PanelSize {
  return last === "minimized" ? "side" : last;
}

export function readPrefs(): AssistantPrefs {
  try {
    return parsePrefs(localStorage.getItem(ASSISTANT_PREFS_KEY));
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function writePrefs(change: Partial<AssistantPrefs>): void {
  try {
    localStorage.setItem(ASSISTANT_PREFS_KEY, JSON.stringify({ ...readPrefs(), ...change }));
  } catch {
    /* Bez úložiště volba platí jen do zavření stránky. */
  }
}
