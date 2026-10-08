type Entry = { dirty: boolean; pending: boolean };
type Dependencies = { entries: () => Entry[]; flush: () => Promise<void>; report: (message: string) => void };

/** Žádný přechod nesmí odmountovat vlastníka konceptu před potvrzením uložení.
 * Blokované formuláře zůstávají otevřené: uživatel v nich zvolí Uložit/Zrušit.
 */
export function createDraftGuard({ entries, flush, report }: Dependencies) {
  let busy = false;
  return async (change: () => void): Promise<boolean> => {
    if (busy) return false;
    busy = true; report("");
    try {
      if (entries().some(entry => entry.dirty || entry.pending)) await flush();
      if (entries().some(entry => entry.dirty || entry.pending)) throw new Error("Koncept není potvrzený jako uložený. Uložte nebo zrušte změny ve formuláři.");
      change(); return true;
    } catch (error) {
      report(error instanceof Error ? error.message : String(error)); return false;
    } finally { busy = false; }
  };
}
