// Přerušení hlasem (barge-in): když člověk během čtení odpovědi promluví, Pletor ztichne a poslouchá.
// Mikrofon má zapnuté potlačení ozvěny (`openMicLevel`), takže vlastní hlas z reproduktorů je u mikrofonu slabý;
// přesto se hlas bere za řeč člověka až po `BARGE_HOLD_MS` souvislé hlasitosti nad prahem a nad vlastním hlasem.
import { useEffect, type RefObject } from "react";
import type { MicLevel } from "./voice-input";

export const BARGE_LEVEL = 0.3;
export const BARGE_HOLD_MS = 350;

/** `(mikrofon, vlastní hlas, čas) → true`, jakmile hlasitost drží nad prahem dost dlouho. */
export function createBargeDetector(level = BARGE_LEVEL, hold = BARGE_HOLD_MS) {
  let since: number | null = null;
  return (mic: number, own: number, now: number): boolean => {
    if (mic < Math.max(level, own * 0.9)) { since = null; return false; }
    since ??= now;
    return now - since >= hold;
  };
}

/** Za čtení hlídá mikrofon a při řeči člověka zavolá `onBarge` (jednou; pak se `active` vrátí na false). */
export function useBargeIn(active: boolean, mic: RefObject<MicLevel | null>, own: () => number | null, onBarge: () => void) {
  useEffect(() => {
    if (!active) return;
    const hears = createBargeDetector();
    const timer = setInterval(() => {
      const level = mic.current?.level();
      if (level !== undefined && hears(level, own() ?? 0, performance.now())) onBarge();
    }, 50);
    return () => clearInterval(timer);
  }, [active, mic, own, onBarge]);
}
