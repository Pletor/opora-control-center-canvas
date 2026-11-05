/**
 * Volby popupu Poslech jsou volba aplikace, ne projektu: jeden klíč pro všechny projekty.
 * `wakeOnly`: reaguje jen věta s oslovením (wake-word.ts). `position`: kam člověk popup odtáhl (`null` = výchozí roh).
 * Samotný přepínač Poslech se neukládá: po startu OPORY je vždy vypnutý, mikrofon se nikdy nezapne sám.
 */
import type { Point } from "./popup-position";

export const LISTEN_PREFS_KEY = "opora:pletor:listen:v1";

export type ListenPrefs = { wakeOnly: boolean; position: Point | null };
export const DEFAULT_LISTEN_PREFS: ListenPrefs = { wakeOnly: false, position: null };

const isPoint = (value: unknown): value is Point =>
  !!value && typeof value === "object" && Number.isFinite((value as Point).x) && Number.isFinite((value as Point).y);

export function parseListenPrefs(raw: string | null): ListenPrefs {
  try {
    const value = JSON.parse(raw ?? "null");
    if (value && typeof value === "object")
      return { wakeOnly: value.wakeOnly === true, position: isPoint(value.position) ? { x: value.position.x, y: value.position.y } : null };
  } catch {
    /* Poškozené volby nejsou data projektu. */
  }
  return { ...DEFAULT_LISTEN_PREFS };
}

export function readListenPrefs(): ListenPrefs {
  try {
    return parseListenPrefs(localStorage.getItem(LISTEN_PREFS_KEY));
  } catch {
    return { ...DEFAULT_LISTEN_PREFS };
  }
}

export function writeListenPrefs(prefs: ListenPrefs): void {
  try {
    localStorage.setItem(LISTEN_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* Bez úložiště volba platí jen do zavření stránky. */
  }
}
