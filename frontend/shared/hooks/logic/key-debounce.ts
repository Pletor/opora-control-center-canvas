// Jedna editace mění revizi víckrát za sebou (optimistický zápis, odpověď serveru, doběhlé refetche).
// Debounce změn klíčů sloučí takovou dávku do jednoho obnovení pollingu místo jednoho na každou změnu.
// Bez Reactu; `usePolling` ho jen napojí na komponentu.

export type KeyDebouncer = { push: (keys: readonly unknown[]) => void; cancel: () => void };

const sameKeys = (a: readonly unknown[], b: readonly unknown[]) => a.length === b.length && a.every((value, index) => Object.is(value, b[index]));

export function createKeyDebouncer(
  initial: readonly unknown[], ms: number, fire: () => void,
  setTimer: (fn: () => void, ms: number) => ReturnType<typeof setTimeout> = (fn, delay) => setTimeout(fn, delay),
  clearTimer: (timer: ReturnType<typeof setTimeout>) => void = (timer) => clearTimeout(timer),
): KeyDebouncer {
  let last = initial;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const cancel = () => { if (timer !== undefined) clearTimer(timer); timer = undefined; };
  return {
    push(keys) {
      if (sameKeys(last, keys)) return;
      last = keys;
      cancel();
      timer = setTimer(() => { timer = undefined; fire(); }, ms);
    },
    cancel,
  };
}
