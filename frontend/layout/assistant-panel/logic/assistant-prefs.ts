/**
 * Preference panelu jsou volba aplikace, ne projektu: jeden klíč pro všechny projekty.
 * Drží jen velikost panelu (minimalizovat, vpravo, celá plocha). Starší záznamy s dalšími poli
 * (model, rozsah, kanál dřívějšího asistenta) se čtou dál, jejich pole se ignorují.
 */
export const ASSISTANT_PREFS_KEY = "opora:assistant:v1";

export type PanelSize = "minimized" | "side" | "full";
export const SIZES: PanelSize[] = ["minimized", "side", "full"];

export type AssistantPrefs = { size: PanelSize };
export const DEFAULT_PREFS: AssistantPrefs = { size: "side" };

/** Uložený JSON → platné preference; neznámé nebo poškozené hodnoty dostanou výchozí. */
export function parsePrefs(raw: string | null): AssistantPrefs {
  try {
    const value = JSON.parse(raw ?? "null");
    if (value && typeof value === "object") return { size: SIZES.includes(value.size) ? value.size : DEFAULT_PREFS.size };
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
