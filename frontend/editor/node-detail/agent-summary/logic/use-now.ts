// Hodiny pro relativní časy („před 3 min“): stačí tik jednou za minutu, přesnější čas by jen zbytečně
// překresloval stránku. Rodič hodnotu rozdá dílkům v props, dílky si čas nikdy neberou samy.
import { useEffect, useState } from "react";

export const NOW_TICK_MS = 60_000;

export function useNow(tickMs: number = NOW_TICK_MS): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), tickMs);
    return () => window.clearInterval(timer);
  }, [tickMs]);
  return now;
}
