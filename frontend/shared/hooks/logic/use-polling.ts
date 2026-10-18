// React napojení sdíleného polleru (`poller.ts`): jeden poller na komponentu po celou dobu, kdy je
// `enabled`. Změna `refreshKeys` (revize stavu, projekt; porovnání jako závislosti efektu) nespouští
// nový poller, jen požádá o refresh: když dotaz běží, další se spustí až po něm. `run` se čte vždy
// aktuální, takže smí záviset na props.
import { useEffect, useMemo, useRef } from "react";
import { createPoller, type Poller } from "./poller";
import { createKeyDebouncer, type KeyDebouncer } from "./key-debounce";

export type PollingOptions = { intervalMs: number | (() => number); enabled?: boolean; refreshKeys?: readonly unknown[]; immediate?: boolean;
  /** Klíče, jejichž změny se sloučí (debounce `debounceMs`): revize stavu, které se při jedné editaci mění víckrát. */
  debouncedKeys?: readonly unknown[]; debounceMs?: number };

export function sameKeys(a: readonly unknown[], b: readonly unknown[]) {
  return a.length === b.length && a.every((value, index) => Object.is(value, b[index]));
}

export function usePolling(run: () => Promise<unknown>, { intervalMs, enabled = true, refreshKeys = [], immediate = true, debouncedKeys = [], debounceMs = 400 }: PollingOptions) {
  const latest = useRef(run);
  useEffect(() => { latest.current = run; });
  // Funkční interval se čte vždy aktuální; nový poller vzniká jen při změně čísla, ne funkce.
  const pause = useRef(intervalMs);
  useEffect(() => { pause.current = intervalMs; });
  const dynamic = typeof intervalMs === "function";
  const poller = useRef<Poller | null>(null);
  const seen = useRef(refreshKeys);
  useEffect(() => {
    if (!enabled) return;
    // Start sám načítá; refresh za klíče ze stejného renderu by byl druhý dotaz navíc.
    seen.current = refreshKeys;
    const interval = dynamic ? () => { const value = pause.current; return typeof value === "function" ? value() : value; } : (intervalMs as number);
    const current = createPoller({ run: () => latest.current(), intervalMs: interval, immediate });
    poller.current = current;
    current.start();
    return () => { current.stop(); if (poller.current === current) poller.current = null; };
  }, [enabled, dynamic ? "dynamic" : intervalMs, immediate]);
  useEffect(() => {
    if (sameKeys(seen.current, refreshKeys)) return;
    seen.current = refreshKeys;
    void poller.current?.refresh();
  });
  // Změna debouncedKeys požádá o refresh až po `debounceMs` ticha; úklid zruší čekající dotaz.
  const debouncer = useRef<KeyDebouncer | null>(null);
  if (!debouncer.current) debouncer.current = createKeyDebouncer(debouncedKeys, debounceMs, () => { void poller.current?.refresh(); });
  useEffect(() => { debouncer.current?.push(debouncedKeys); });
  useEffect(() => () => debouncer.current?.cancel(), []);
  return useMemo(() => ({
    refresh: () => poller.current?.refresh() ?? Promise.resolve(),
    poke: () => poller.current?.poke() ?? Promise.resolve(),
  }), []);
}
