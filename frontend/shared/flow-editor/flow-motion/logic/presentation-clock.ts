// Prezentační hodiny pohybu Studia, převzaté z prototypu Architektura projektu (`prototype/animations.mjs`,
// `PresentationClock`, rozbor `analysis/animation-timing-implementation.md`). Oddělují čas na obrazovce od zdroje
// pohybu: běžící hodiny přičítají uplynulý čas stěny, pozastavené (skrytý dokument, omezený pohyb) nepřičítají nic,
// takže se po návratu nepřehraje, co člověk neviděl. Změna kontextu (`key`, např. úroveň plátna) nebo pokles ticku
// začne od nuly. Pozastavený krok ticku posune fázi jednou o 280 ms (vrstva MODEL, docs/studio.md §5); Skutečnost
// tick nepoužívá a hodiny jen běží. Milisekundy popisují prezentaci, ne měření projektu. Čistá logika bez DOM.

/** Posun fáze za jeden pozastavený krok ticku (ms), odvozený v prototypu. */
export const PAUSED_TICK_MS = 280;

export type ClockFrame = { running?: boolean; tick?: number; key?: string; suspended?: boolean };

export class PresentationClock {
  /** Čas prezentace (ms) od začátku kontextu. */
  time = 0;
  /** Čas vnitřního markeru; nuluje se při pauze. */
  sweepTime = 0;
  last: number | null = null;
  running = false;
  tick = 0;
  key: string | null = null;

  /** Přičte uplynulý čas stěny, jen když hodiny běží a nejsou pozastavené. */
  advance(now: number, suspended = false): void {
    if (this.last !== null && this.running && !suspended) {
      const elapsed = Math.max(0, now - this.last);
      this.time += elapsed;
      this.sweepTime += elapsed;
    }
    this.last = now;
  }

  /** Nový snímek zdroje: běží/stojí, tick a identita kontextu. */
  setFrame({ running = false, tick = 0, key = "model", suspended = false }: ClockFrame, now: number): void {
    this.advance(now, suspended);
    if (key !== this.key || tick < this.tick || tick === 0) { this.time = 0; this.sweepTime = 0; this.tick = 0; }
    if (!running && tick > this.tick) this.time += (tick - this.tick) * PAUSED_TICK_MS;
    if (!running || !this.running) this.sweepTime = 0;
    this.running = running; this.tick = tick; this.key = key;
  }

  /** Po pauze (skrytý dokument, změna preference) začne další přírůstek od teď, ne od posledního snímku. */
  resync(now: number): void {
    this.last = now;
  }
}
