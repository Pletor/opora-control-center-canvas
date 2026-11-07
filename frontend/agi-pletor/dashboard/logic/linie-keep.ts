/**
 * Stálá poloha výběru a pořadí Esc (docs/navrhy/2026-11-06-linie-rebrand.md §6). Přepnutí vrstvy, sbalení nebo nová
 * data nesmí odsunout vybranou kuličku: posuvný prvek se dorovná o tolik, o kolik se kulička svisle pohnula.
 */
export type Mark = { id: string; y: number } | null;

/** Nový `scrollTop`: jen když jde o tutéž kuličku a ta stále existuje; nový výběr ani zmizelá kulička nic nemění. */
export function keepScroll(before: Mark, after: Mark, scrollTop: number): number {
  if (!before || !after || before.id !== after.id) return scrollTop;
  return Math.max(0, scrollTop + (after.y - before.y));
}

export type Layers = { renaming: boolean; trace: boolean; commit: boolean; detail: boolean; full: boolean };
export type EscTarget = keyof Layers | null;

/** Esc zavře nejbližší vrstvu: přejmenování → Cesta → commit → detail → celá obrazovka → nic (pak ho dostane Velín). */
export function escTarget(open: Layers): EscTarget {
  return (["renaming", "trace", "commit", "detail", "full"] as const).find((layer) => open[layer]) ?? null;
}
