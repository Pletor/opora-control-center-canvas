import { useSyncExternalStore } from "react";

type Scheduler = { now: () => number; setInterval: (callback: () => void, milliseconds: number) => ReturnType<typeof setInterval>; clearInterval: (timer: ReturnType<typeof setInterval>) => void };

/** Jediný čas na celé plátno: interval běží jen dokud ho sleduje aspoň jedna karta. */
export function createLeaseClock(scheduler: Scheduler = { now: Date.now, setInterval, clearInterval }) {
  let now = scheduler.now();
  let timer: ReturnType<typeof setInterval> | undefined;
  const listeners = new Set<() => void>();
  const tick = () => { now = scheduler.now(); listeners.forEach(listener => listener()); };
  return {
    getSnapshot: () => now,
    subscribe(listener: () => void) {
      listeners.add(listener);
      if (!timer) timer = scheduler.setInterval(tick, 1000);
      return () => {
        listeners.delete(listener);
        if (!listeners.size && timer) { scheduler.clearInterval(timer); timer = undefined; }
      };
    },
  };
}

const leaseClock = createLeaseClock();
/** Subscribe every lease display to the same singleton ticker rather than one timer per card. */
export function useLeaseClock(): number {
  return useSyncExternalStore(leaseClock.subscribe, leaseClock.getSnapshot, leaseClock.getSnapshot);
}
