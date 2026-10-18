// Odpočet do dalšího ručního ověření webu („Další ověření za 18 s“). Hodiny tikají jen během
// odpočtu; jakmile vyprší, stojí. Nový čas kontroly hostu odpočet spustí znovu.
import { useEffect, useState } from "react";
import { refreshWait } from "./web-status";

export function useRefreshWait(checkedAt: string | null | undefined): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { setNow(Date.now()); }, [checkedAt]);
  const wait = refreshWait(checkedAt, now);
  const counting = wait > 0;
  useEffect(() => {
    if (!counting) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [counting]);
  return wait;
}
