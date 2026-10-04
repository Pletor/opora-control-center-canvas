/**
 * Řádek o tom, co model právě generuje beze slov: „Přemýšlí… 3 kB“ nebo „Píše Write… 24 kB“.
 * Čistá funkce; vstup je `progress` z reduceru (`assistant-events.ts`).
 */
import type { Progress } from "./assistant-events";

export function progressLabel(progress: Progress): string {
  const size = `${Math.round(progress.chars / 1000)} kB`;
  if (progress.kind === "thinking") return `Přemýšlí… ${size}`;
  return `Píše ${progress.name || "nástroj"}… ${size}`;
}
