/**
 * Předvolby Linie uložené jednou pro aplikaci (`localStorage`, nikdy per projekt): šířka sloupce názvů a vrstvy.
 * Vrstvy, pro které board zatím nenese data, se dají zapnout, ale lišta je ukáže šedě „bez zdroje“.
 */
export const NAMES_KEY = "pletor.linie.names";
export const LAYERS_KEY = "pletor.linie.layers";
export const NAMES_MIN = 160;
export const NAMES_MAX = 420;
export const NAMES_DEFAULT = 260;

export type LayerId = "commits" | "plans" | "tags" | "worktree";
export type LayerState = Record<LayerId, boolean>;
export const LAYER_LABEL: Record<LayerId, string> = { commits: "commity všech kuliček", plans: "plány ostatních kuliček", tags: "tagy", worktree: "worktree" };
const OFF: LayerState = { commits: false, plans: false, tags: false, worktree: false };

export const clampNames = (width: number) => Math.round(Math.min(NAMES_MAX, Math.max(NAMES_MIN, width)));

type Read = Pick<Storage, "getItem"> | undefined;

export function readNames(storage: Read): number {
  const value = Number(storage?.getItem(NAMES_KEY));
  return Number.isFinite(value) && value > 0 ? clampNames(value) : NAMES_DEFAULT;
}

export function readLayers(storage: Read): LayerState {
  try {
    const value: unknown = JSON.parse(storage?.getItem(LAYERS_KEY) ?? "{}");
    const saved = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
    return Object.fromEntries(Object.keys(OFF).map((id) => [id, saved[id] === true])) as LayerState;
  } catch {
    return { ...OFF };
  }
}

/** Zápis bez úložiště (soukromé okno) tiše selže: předvolba pak platí do obnovení stránky. */
export function save(key: string, value: unknown) {
  try { globalThis.localStorage?.setItem(key, typeof value === "string" ? value : JSON.stringify(value)); } catch { /* bez úložiště */ }
}
