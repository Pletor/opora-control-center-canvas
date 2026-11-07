/**
 * Předvolby Linie uložené jednou pro aplikaci (`localStorage`, nikdy per projekt): šířka sloupce názvů, vrstvy a celá obrazovka.
 * Výchozí pohled = větve, kuličky, souhrn a ověřené začlenění (+ pilulky PR a tagy); commity, worktree a plány
 * ostatních kuliček jsou vypnuté a pro vybranou kuličku se ukážou vždy.
 */
export const NAMES_KEY = "pletor.linie.names";
export const LAYERS_KEY = "pletor.linie.layers";
export const FULL_KEY = "pletor.linie.full";
export const NAMES_MIN = 160;
export const NAMES_MAX = 420;
export const NAMES_DEFAULT = 260;

export type LayerId = "commits" | "worktree" | "plans" | "prs" | "tags";
export type LayerState = Record<LayerId, boolean>;
export const LAYER_LABEL: Record<LayerId, string> = { commits: "Commity všech kuliček", worktree: "Worktree agentů", plans: "Plány všech kuliček", prs: "PR pilulky", tags: "Tagy a nasazení" };
export const LAYER_DEFAULT: LayerState = { commits: false, worktree: false, plans: false, prs: true, tags: true };

export const clampNames = (width: number) => Math.round(Math.min(NAMES_MAX, Math.max(NAMES_MIN, width)));

type Read = Pick<Storage, "getItem"> | undefined;

export function readNames(storage: Read): number {
  const value = Number(storage?.getItem(NAMES_KEY));
  return Number.isFinite(value) && value > 0 ? clampNames(value) : NAMES_DEFAULT;
}

/** Celá obrazovka jen při uloženém "true"; cokoli jiného (i chybějící úložiště) = zasazená ve Velínu. */
export const readFull = (storage: Read) => storage?.getItem(FULL_KEY) === "true";

/** Uložená hodnota platí jen jako boolean; chybějící klíč má výchozí, rozbitý zápis = výchozí vše. */
export function readLayers(storage: Read): LayerState {
  try {
    const value: unknown = JSON.parse(storage?.getItem(LAYERS_KEY) ?? "{}");
    const saved = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
    return Object.fromEntries((Object.keys(LAYER_DEFAULT) as LayerId[]).map((id) => [id, typeof saved[id] === "boolean" ? saved[id] : LAYER_DEFAULT[id]])) as LayerState;
  } catch {
    return { ...LAYER_DEFAULT };
  }
}

/** Zápis bez úložiště (soukromé okno) tiše selže: předvolba pak platí do obnovení stránky. */
export function save(key: string, value: unknown) {
  try { globalThis.localStorage?.setItem(key, typeof value === "string" ? value : JSON.stringify(value)); } catch { /* bez úložiště */ }
}
