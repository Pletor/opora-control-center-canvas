/** Stabilní data pro memoizovanou kartu: obsah rozhoduje o renderu, callbacky zůstávají vždy čerstvé. */
type Callback = (...args: never[]) => unknown;
type CallbackHolder = { current: Callback };
const holders = new WeakMap<Callback, CallbackHolder>();

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function sameShape(left: unknown, right: unknown): boolean {
  if (typeof left === "function" || typeof right === "function") return typeof left === typeof right;
  if (Object.is(left, right)) return true;
  if (Array.isArray(left) || Array.isArray(right))
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((item, index) => sameShape(item, right[index]));
  if (!isRecord(left) || !isRecord(right)) return false;
  const leftKeys = Object.keys(left), rightKeys = Object.keys(right);
  return leftKeys.length === rightKeys.length && leftKeys.every(key => Object.hasOwn(right, key) && sameShape(left[key], right[key]));
}

function forwarded(callback: Callback): Callback {
  const holder: CallbackHolder = { current: callback };
  const wrapper = ((...args: never[]) => holder.current(...args)) as Callback;
  holders.set(wrapper, holder);
  return wrapper;
}

function copyWithForwarders(value: unknown): unknown {
  if (typeof value === "function") return forwarded(value as Callback);
  if (Array.isArray(value)) return value.map(copyWithForwarders);
  if (isRecord(value)) return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, copyWithForwarders(item)]));
  return value;
}

function refreshCallbacks(stable: unknown, fresh: unknown): void {
  if (typeof fresh === "function") {
    const holder = holders.get(stable as Callback);
    if (holder) holder.current = fresh as Callback;
    return;
  }
  if (Array.isArray(stable) && Array.isArray(fresh)) stable.forEach((item, index) => refreshCallbacks(item, fresh[index]));
  else if (isRecord(stable) && isRecord(fresh)) Object.keys(fresh).forEach(key => refreshCallbacks(stable[key], fresh[key]));
}

/** Reuse `previous` when non-callback card data are equal, while callback wrappers forward to the latest poll. */
export function stabilizeCardData<T extends Record<string, unknown>>(previous: T | undefined, fresh: T): T {
  if (previous && sameShape(previous, fresh)) {
    refreshCallbacks(previous, fresh);
    return previous;
  }
  return copyWithForwarders(fresh) as T;
}

export const sameCardData = sameShape;
