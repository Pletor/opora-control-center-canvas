import { useEffect, useRef, useState } from "react";

export const addedIds = (before: string[], after: string[]) => {
  const known = new Set(before);
  return after.filter(id => !known.has(id));
};

/** Initial data is not new work. Pulse only identities added to a mounted card. */
export function useAddedPulse(ids: string[]) {
  const previous = useRef(ids);
  const [recent, setRecent] = useState<string[]>([]);
  const key = JSON.stringify(ids);
  useEffect(() => {
    const added = addedIds(previous.current, ids);
    previous.current = ids;
    if (added.length) setRecent(added);
  }, [key]);
  useEffect(() => {
    if (!recent.length) return;
    const timer = window.setTimeout(() => setRecent([]), 2400);
    return () => window.clearTimeout(timer);
  }, [recent]);
  return recent;
}
