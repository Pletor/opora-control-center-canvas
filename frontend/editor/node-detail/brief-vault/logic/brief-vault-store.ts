// Jeden sdílený zdroj stromu schránky pro celé UI (plátno, inspektor, záložka, pop-up). Dřív si každý
// panel tahal GET /api/brief-vault sám a každých 15 s (tři pollery najednou). Teď: jeden záznam na
// projekt a prostor, jeden poller (sdílený vzor `createPoller`), požadavky na obnovu ze stejného okamžiku
// (změna stavu plátna) se slijí do jednoho dotazu. Bez Reactu; hook `useBriefVault` se jen přihlásí k odběru.
import type { VaultTree } from "./brief-vault-model";
import { createPoller, type Poller, type VisibilitySource } from "@/shared/hooks/logic/poller";

export type VaultSnapshot = { tree?: VaultTree; error: string };
type Timer = ReturnType<typeof setTimeout>;
type Entry = VaultSnapshot & {
  listeners: Set<() => void>;
  pending?: Timer;
  // Sdílený poller (shared/hooks/logic/poller.ts): jeden dotaz najednou, požadavek během běhu se
  // provede hned po něm, ve skryté záložce stojí.
  poller: Poller;
};

export type VaultStoreOptions = {
  fetchTree: (project: string, workspace: string) => Promise<VaultTree>;
  /** Obnova na pozadí (ms); 0 = vypnuto. */
  pollMs?: number;
  /** Okno, ve kterém se víc požadavků na obnovu slije do jednoho dotazu (ms). */
  debounceMs?: number;
  setTimer?: (fn: () => void, ms: number) => Timer;
  clearTimer?: (timer: Timer) => void;
  visibility?: VisibilitySource;
};

export function createVaultStore(options: VaultStoreOptions) {
  const { fetchTree, pollMs = 15000, debounceMs = 200, visibility } = options;
  const setTimer = options.setTimer ?? ((fn, ms) => setTimeout(fn, ms));
  const clearTimer = options.clearTimer ?? ((timer) => clearTimeout(timer));
  const entries = new Map<string, Entry>();
  const keyOf = (project: string, workspace: string) => JSON.stringify([project, workspace]);

  function entry(project: string, workspace: string): Entry {
    const key = keyOf(project, workspace);
    let found = entries.get(key);
    if (!found) {
      const item: Entry = { error: "", listeners: new Set(), poller: undefined as unknown as Poller };
      item.poller = createPoller({
        run: () => fetchTree(project, workspace)
          .then((tree) => { item.tree = tree; item.error = ""; })
          .catch((e: unknown) => { item.error = e instanceof Error ? e.message : String(e); })
          .finally(() => emit(item)),
        intervalMs: pollMs, visibility, setTimer, clearTimer,
      });
      entries.set(key, item);
      found = item;
    }
    return found;
  }

  function emit(item: Entry) { item.listeners.forEach((listener) => listener()); }

  return {
    snapshot(project: string, workspace: string): VaultSnapshot {
      const item = entries.get(keyOf(project, workspace));
      return item ? { tree: item.tree, error: item.error } : { error: "" };
    },
    subscribe(project: string, workspace: string, listener: () => void): () => void {
      const item = entry(project, workspace);
      item.listeners.add(listener);
      // První odběratel rozběhne poller; načte hned, jen když strom ještě není a nic se nechystá.
      if (item.listeners.size === 1) item.poller.start(!item.tree && !item.pending);
      return () => {
        item.listeners.delete(listener);
        if (!item.listeners.size) item.poller.stop();
      };
    },
    /** Požadavek na obnovu (změna stavu plátna, zápis do schránky); slije se s ostatními v okně `debounceMs`. */
    refresh(project: string, workspace: string) {
      const item = entry(project, workspace);
      if (item.pending) return;
      item.pending = setTimer(() => { item.pending = undefined; void item.poller.refresh(); }, debounceMs);
    },
    /** Okamžité načtení (po vlastním zápisu); vrací slib dokončení. */
    reload(project: string, workspace: string) { return entry(project, workspace).poller.refresh(); },
  };
}

export type VaultStore = ReturnType<typeof createVaultStore>;
