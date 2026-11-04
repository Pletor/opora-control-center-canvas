// Pole uzlu plátna toku v inspektoru (kontrakt knihovny §1): schémata vstupu a výstupu jsou JSON objekt (JSON Schema
// nebo příklad), ukázková data libovolný JSON, opakování `{maxTries ≥ 1, waitMs ≥ 0}`. Stejná pravidla hlídá
// `backend/flow/graph_check.py`; tady se chyba ukáže u pole a do grafu nejde. Prázdné pole = pole odebrat.
import type { Parsed } from "./inspector-fields";

export const pretty = (value: unknown) => value === undefined ? "" : JSON.stringify(value, null, 2);

/** `object`: schéma musí být objekt; jinak (ukázková data) stačí platný JSON. */
export function parseJsonField(raw: string, object: boolean): Parsed {
  if (!raw.trim()) return { value: undefined };
  let value: unknown;
  try { value = JSON.parse(raw); } catch { return { error: "Neplatný JSON." }; }
  if (object && (!value || typeof value !== "object" || Array.isArray(value))) return { error: "Schéma je JSON objekt (JSON Schema nebo příklad)." };
  return { value };
}

/** Opakování při chybě: obě pole prázdná = bez opakování; jinak celé číslo pokusů ≥ 1 a čekání v ms ≥ 0. */
export function parseRetry(tries: string, wait: string): Parsed {
  if (!tries.trim() && !wait.trim()) return { value: undefined };
  const maxTries = Number(tries), waitMs = wait.trim() ? Number(wait) : 0;
  if (!Number.isInteger(maxTries) || maxTries < 1) return { error: "Počet pokusů je celé číslo od 1." };
  if (!Number.isFinite(waitMs) || waitMs < 0) return { error: "Čekání je počet milisekund od 0." };
  return { value: { maxTries, waitMs } };
}
