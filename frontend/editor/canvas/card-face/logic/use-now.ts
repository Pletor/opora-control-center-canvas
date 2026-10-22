import { useEffect, useState } from "react";

/** Aktuální čas po `ms`; vypnuté hodiny nic neplánují (karta bez lease se nepřekresluje). */
export function useNow(ms: number, enabled: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!enabled) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(timer);
  }, [ms, enabled]);
  return now;
}
