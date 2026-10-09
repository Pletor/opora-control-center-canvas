// Jeden sdílený zdroj stromu schránky pro celé UI (plátno, inspektor, záložka, pop-up). Dřív si každý
// panel tahal GET /api/brief-vault sám a každých 15 s (tři pollery najednou). Teď: jeden záznam na
// projekt a prostor, jeden poller, požadavky na obnovu ze stejného okamžiku (změna stavu plátna) se
// slijí do jednoho dotazu. Bez Reactu; hook `useBriefVault` se jen přihlásí k odběru.
import type { VaultTree } from "./brief-vault-model";

export type VaultSnapshot = { tree?: VaultTree; error: string };
type Timer = ReturnType<typeof setTimeout>;
type Entry = VaultSnapshot & {
  listeners: Set<() => void>;
  poll?: Timer;
  pending?: Timer;
  inflight?: Promise<void>;
  again: boolean;
};

export type VaultStoreOptions = {
  fetchTree: (project: string, workspace: string) => Promise<VaultTree>;
  /** Obnova na pozadí (ms); 0 = vypnuto. */
  pollMs?: number;
  /** Okno, ve kterém se víc požadavků na obnovu slije do jednoho dotazu (ms). */
  debounceMs?: number;
  setTimer?: (fn: () => void, ms: number) => Timer;
  clearTimer?: (timer: Timer) => void;
};

export function createVaultStore(options: VaultStoreOptions) {
  const { fetchTree, pollMs = 15000, debounceMs = 200 } = options;
  const setTimer = options.setTimer ?? ((fn, ms) => setTimeout(fn, ms));
  const clearTimer = options.clearTimer ?? ((timer) => clearTimeout(timer));
  const entries = new Map<string, Entry>();
  const keyOf = (project: string, workspace: string) => JSON.stringify([project, workspace]);

  function entry(project: string, workspace: string): Entry {
    const key = keyOf(project, workspace);
    let found = entries.get(key);
    if (!found) { found = { error: "", listeners: new Set(), again: false }; entries.set(key, found); }
    return found;
  }

  function emit(item: Entry) { item.listeners.forEach((listener) => listener()); }

  function schedulePoll(project: string, workspace: string, item: Entry) {
    if (item.poll) clearTimer(item.poll);
    item.poll = undefined;
    if (pollMs > 0 && item.listeners.size) item.poll = setTimer(() => { void load(project, workspace); }, pollMs);
  }

  /** Jeden dotaz najednou; požadavek během běhu se provede hned po něm (nic se neztratí). */
  function load(project: string, workspace: string): Promise<void> {
    const item = entry(project, workspace);
    if (item.inflight) { item.again = true; return item.inflight; }
    item.inflight = fetchTree(project, workspace)
      .then((tree) => { item.tree = tree; item.error = ""; })
      .catch((e: unknown) => { item.error = e instanceof Error ? e.message : String(e); })
      .finally(() => {
        item.inflight = undefined;
        emit(item);
        if (item.again) { item.again = false; void load(project, workspace); }
        else schedulePoll(project, workspace, item);
      });
    return item.inflight;
  }

  return {
    snapshot(project: string, workspace: string): VaultSnapshot {
      const item = entries.get(keyOf(project, workspace));
      return item ? { tree: item.tree, error: item.error } : { error: "" };
    },
    subscribe(project: string, workspace: string, listener: () => void): () => void {
      const item = entry(project, workspace);
      item.listeners.add(listener);
      if (!item.tree && !item.inflight && !item.pending) void load(project, workspace);
      else if (!item.poll && !item.inflight) schedulePoll(project, workspace, item);
      return () => {
        item.listeners.delete(listener);
        if (!item.listeners.size && item.poll) { clearTimer(item.poll); item.poll = undefined; }
      };
    },
    /** Požadavek na obnovu (změna stavu plátna, zápis do schránky); slije se s ostatními v okně `debounceMs`. */
    refresh(project: string, workspace: string) {
      const item = entry(project, workspace);
      if (item.pending) return;
      item.pending = setTimer(() => { item.pending = undefined; void load(project, workspace); }, debounceMs);
    },
    /** Okamžité načtení (po vlastním zápisu); vrací slib dokončení. */
    reload(project: string, workspace: string) { return load(project, workspace); },
  };
}

export type VaultStore = ReturnType<typeof createVaultStore>;
