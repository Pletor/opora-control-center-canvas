/** Úložiště jen v rozsahu, který nav potřebuje (stačí `localStorage`). */
type NavStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export const NAV_KEY = "pletor.nav";

/** Je levé menu zasunuté? Jedno nastavení pro aplikaci; nedostupné úložiště = roztažené. */
export function readNarrow(storage: NavStorage): boolean {
  try { return storage.getItem(NAV_KEY) === "narrow"; } catch { return false; }
}

/** Zapíše zasunutí; roztažené stav maže, aby klíč nezůstával. */
export function writeNarrow(storage: NavStorage, narrow: boolean): void {
  try { if (narrow) storage.setItem(NAV_KEY, "narrow"); else storage.removeItem(NAV_KEY); } catch { /* soukromý režim: zasunutí platí jen do obnovení */ }
}
