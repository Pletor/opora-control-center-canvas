import { api } from "@/shared/types/logic/types";

type Subscriber = { receive: (value: unknown) => void; fail: (error: unknown) => void };
type Query = { subscribers: Set<Subscriber>; stop: () => void; refresh: () => Promise<void> };
const queries = new Map<string, Query>();

/** Jeden časovač a jeden request na URL. Skryté okno nic nepolluje, návrat obnoví data. */
export function watchQuery<T>(url: string, milliseconds: number, receive: (value: T) => void, fail: (error: unknown) => void) {
  const subscriber: Subscriber = { receive: value => receive(value as T), fail };
  let query = queries.get(url);
  if (!query) {
    const subscribers = new Set<Subscriber>();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let running = false, active = true;
    const visible = () => typeof document === "undefined" || document.visibilityState !== "hidden";
    async function refresh() {
      if (!active || running || !visible()) return;
      clearTimeout(timer);
      running = true;
      try {
        const value = await api<T>(url);
        if (active) for (const item of subscribers) item.receive(structuredClone(value));
      } catch (error) {
        if (active) for (const item of subscribers) item.fail(error);
      } finally {
        running = false;
        if (active && visible()) timer = setTimeout(refresh, milliseconds);
      }
    }
    const onVisibility = () => { clearTimeout(timer); if (visible()) void refresh(); };
    if (typeof document !== "undefined") document.addEventListener("visibilitychange", onVisibility);
    query = { subscribers, refresh, stop: () => {
      active = false; clearTimeout(timer);
      if (typeof document !== "undefined") document.removeEventListener("visibilitychange", onVisibility);
    } };
    queries.set(url, query);
    subscribers.add(subscriber);
    void refresh();
  } else {
    query.subscribers.add(subscriber);
    void query.refresh();
  }
  const owner = query;
  return () => {
    owner.subscribers.delete(subscriber);
    if (!owner.subscribers.size) { owner.stop(); if (queries.get(url) === owner) queries.delete(url); }
  };
}
