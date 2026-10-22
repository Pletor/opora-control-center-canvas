// Proud událostí s tlačítkem „Pozastavit čtení“: data přicházejí dál, ale seznam stojí, aby se dal číst.
// Nové události čekají v `pending` a lišta ukazuje jejich počet; „Pokračovat“ je přidá najednou.
// Dedupe podle `eventId` platí přes oba seznamy, takže opakované doručení nic nezdvojí.
import { mergeEvents, type FlowEvent } from "./process-event";

export type StreamBuffer = { shown: FlowEvent[]; pending: FlowEvent[]; paused: boolean };
export const KEEP_STREAM = 300;

export const emptyBuffer = (): StreamBuffer => ({ shown: [], pending: [], paused: false });

export function ingest(buffer: StreamBuffer, incoming: FlowEvent[]): StreamBuffer {
  const known = new Set([...buffer.shown, ...buffer.pending].map((event) => event.key));
  const fresh = incoming.filter((event) => !known.has(event.key));
  if (!fresh.length) return buffer;
  if (buffer.paused) return { ...buffer, pending: mergeEvents(buffer.pending, fresh, KEEP_STREAM) };
  return { ...buffer, shown: mergeEvents(buffer.shown, fresh, KEEP_STREAM) };
}

export const pause = (buffer: StreamBuffer): StreamBuffer => buffer.paused ? buffer : { ...buffer, paused: true };

export function resume(buffer: StreamBuffer): StreamBuffer {
  return { shown: mergeEvents(buffer.shown, buffer.pending, KEEP_STREAM), pending: [], paused: false };
}

export type StreamFilter = { card: string; worker: string };
/** Řádky proudu: nejnovější nahoře, filtr podle karty a pracovníka. */
export function visibleStream(events: FlowEvent[], filter: StreamFilter): FlowEvent[] {
  return events.filter((event) => (!filter.card || event.cardId === filter.card) && (!filter.worker || event.workerId === filter.worker))
    .sort((a, b) => b.id - a.id);
}

/** Pracovníci pro filtr: id a jméno z událostí, bez dvojic. */
export function workerOptions(events: FlowEvent[]) {
  const workers = new Map<string, string>();
  for (const event of events) if (event.workerId && !workers.has(event.workerId)) workers.set(event.workerId, event.workerName || event.workerId);
  return [...workers].map(([id, name]) => ({ id, name }));
}
