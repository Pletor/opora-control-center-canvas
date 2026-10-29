import type { HeartStatus } from "./heart-api";

export type HeartTone = "sleeping" | "working" | "waiting" | "error" | "off";
export type HeartLine = { tone: HeartTone; text: string };

/** ISO čas → „14:05“ v místním čase; neplatný čas zůstane prázdný. */
export function clock(iso: string | null): string {
  const time = iso ? new Date(iso) : null;
  if (!time || Number.isNaN(time.getTime())) return "";
  return `${String(time.getHours()).padStart(2, "0")}:${String(time.getMinutes()).padStart(2, "0")}`;
}

function inputs(count: number): string {
  if (count === 1) return "1 vstup";
  return count < 5 ? `${count} vstupy` : `${count} vstupů`;
}

/**
 * Stav srdce jednou větou: chyba, práce, čekání do času (limit předplatného nebo strop dávek),
 * vstupy těsně před dávkou, nebo spánek. Srdce, které na serveru neběží (`OPORA_HEART=off`), to přizná.
 */
export function statusLine(status: HeartStatus, now: number = Date.now()): HeartLine {
  if (status.error) return { tone: "error", text: `Chyba: ${status.error}` };
  if (status.running) return { tone: "working", text: "Pracuje na dávce" };
  if (!status.enabled) {
    const queued = status.pending > 0 ? ` · čeká ${inputs(status.pending)}` : "";
    return { tone: "off", text: `Srdce na tomto serveru neběží${queued}` };
  }
  if (status.sleeping) return { tone: "waiting", text: `Čeká do ${clock(status.sleepingUntil)} (limit předplatného)` };
  const next = status.nextAllowedAt ? Date.parse(status.nextAllowedAt) : NaN;
  if (status.pending > 0 && next > now) {
    return { tone: "waiting", text: `Čeká do ${clock(status.nextAllowedAt)} · ${inputs(status.pending)}` };
  }
  if (status.pending > 0) return { tone: "working", text: `Probouzí se · ${inputs(status.pending)}` };
  return { tone: "sleeping", text: "Spí, probudí ho zpráva nebo otázka pracovníka" };
}
