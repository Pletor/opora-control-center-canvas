// Pohyb značky pracovníka: nic se nehýbe samo, každý pohyb odpovídá jedné nové události karty.
// Jiná fáze → přesun ze staré buňky (o `shift` buněk), `tool.use` ve stejné fázi → pulz, `fail` → zatřesení.
// První vykreslení (žádný předchozí stav) se nehýbe.
export type MarkerSeen = { phase: number; lastKey: string };
export type MarkerLast = { key: string; kind: string; state: string } | null;
export type MarkerMotion = { shift: number; pulse: boolean; shake: boolean };
export const STILL: MarkerMotion = { shift: 0, pulse: false, shake: false };

export function markerMotion(previous: MarkerSeen | undefined, phase: number, last: MarkerLast): MarkerMotion {
  if (!previous || !last || previous.lastKey === last.key) return STILL;
  const shift = previous.phase - phase;
  return { shift, pulse: shift === 0 && last.kind === "tool.use", shake: last.state === "fail" };
}
