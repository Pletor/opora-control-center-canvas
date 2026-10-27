// Historie editace modelu (zpět / znovu, Ctrl+Z / Ctrl+Shift+Z) jako čistá data: minulost, přítomnost a budoucnost,
// nejvýš 100 kroků jako v prototypu. Psaní do jednoho pole (název, popisek, podmínka) se slévá do jednoho kroku
// podle klíče, aby zpět nevracelo text po písmenech. Revize úložiště v historii nežije, dodá ji uložení.

export const HISTORY_LIMIT = 100;
export type History<M> = { past: M[]; present: M; future: M[]; mergeKey: string | null };

export const historyOf = <M>(present: M): History<M> => ({ past: [], present, future: [], mergeKey: null });

/** Nový krok; stejný model nic nezmění, stejný `mergeKey` jako minule jen přepíše přítomnost. */
export function commit<M>(history: History<M>, next: M, mergeKey: string | null = null): History<M> {
  if (next === history.present) return history;
  if (mergeKey && mergeKey === history.mergeKey) return { ...history, present: next, future: [] };
  return { past: [...history.past, history.present].slice(-HISTORY_LIMIT), present: next, future: [], mergeKey };
}

export function undo<M>(history: History<M>): History<M> {
  if (!history.past.length) return history;
  return { past: history.past.slice(0, -1), present: history.past[history.past.length - 1], future: [history.present, ...history.future], mergeKey: null };
}

export function redo<M>(history: History<M>): History<M> {
  if (!history.future.length) return history;
  return { past: [...history.past, history.present], present: history.future[0], future: history.future.slice(1), mergeKey: null };
}
