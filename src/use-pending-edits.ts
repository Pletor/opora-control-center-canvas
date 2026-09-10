import { useEffect, useRef } from "react";

/**
 * Jedna evidence rozepsané editace pro bloky uzlu i deník.
 *
 * Kontrakt: text patří uživateli, dokud ho server prokazatelně nepřevzal.
 * Draft se zapisuje do sessionStorage okamžitě při psaní, přežije odpojení
 * komponenty (přepnutí uzlu/režimu) i reload karty a maže se výhradně po
 * úspěšném uložení nebo výslovným zahozením. Neúspěšné uložení draft nechává.
 */
export type PendingEdit = { text: string; revision: number };

const STORE_KEY = "opora.pending-edits.v1";
/** Záloha pro prostředí bez sessionStorage; drží alespoň přepnutí uzlu. */
const memory = new Map<string, PendingEdit>();

function store(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function readAll(): Record<string, PendingEdit> {
  const raw = store()?.getItem(STORE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as Record<string, PendingEdit>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeAll(all: Record<string, PendingEdit>) {
  try {
    store()?.setItem(STORE_KEY, JSON.stringify(all));
  } catch {
    // Plné nebo zakázané úložiště nesmí shodit editaci; zůstává paměťová záloha.
  }
}

/** Rozsah draftu je identita editovaného obsahu, ne komponenta. */
export function editScope(kind: string, parts: (string | undefined)[]) {
  return JSON.stringify([kind, ...parts]);
}

export function readPendingEdit(scope: string): PendingEdit | null {
  const saved = readAll()[scope] ?? memory.get(scope) ?? null;
  if (!saved || typeof saved.text !== "string" || typeof saved.revision !== "number") return null;
  return { text: saved.text, revision: saved.revision };
}

export function writePendingEdit(scope: string, edit: PendingEdit) {
  memory.set(scope, edit);
  const all = readAll();
  all[scope] = edit;
  writeAll(all);
}

export function clearPendingEdit(scope: string, expected?: PendingEdit) {
  const current = readPendingEdit(scope);
  if (expected && current && (current.text !== expected.text || current.revision !== expected.revision)) return;
  memory.delete(scope);
  const all = readAll();
  if (!(scope in all)) return;
  delete all[scope];
  writeAll(all);
}

/**
 * Odchod z uzlu/režimu i zavření karty se pokusí čekající uložení dopsat.
 * Draft maže až samotné uložení, takže neúspěšný flush nic neztratí.
 */
export function usePendingFlush(scope: string, flush: () => void) {
  const latest = useRef({ scope, flush });
  // Cleanup starého scope drží vlastní objekt; nový render mu nesmí vyměnit cíl zápisu.
  if (latest.current.scope !== scope) latest.current = { scope, flush };
  else latest.current.flush = flush;
  useEffect(() => {
    const owner = latest.current;
    const leave = () => owner.flush();
    window.addEventListener("pagehide", leave);
    return () => {
      window.removeEventListener("pagehide", leave);
      leave();
    };
  }, [scope]);
}
