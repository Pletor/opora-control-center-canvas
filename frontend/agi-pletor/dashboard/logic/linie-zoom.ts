/**
 * Společná časová souřadnice Linie (docs/navrhy/2026-11-06-linie-rebrand.md §6): x = PAD + (t − t0) · k, kde `k` je
 * px na ms. Měřítko je stav, ne odvozenina šířky okna: mění ho jen kolečko a tlačítka `Vše` / `↻ Výchozí`. Přiblížení
 * kolem kurzoru drží čas pod kurzorem na místě (posun `scrollLeft` jediného posuvného prvku).
 */
export const PAD = 70;
const MIN = 60_000;
export const ZOOM_MAX_SPAN = 15 * MIN; // nejbližší pohled: 15 min přes celé plátno

export type Scale = { t0: number; k: number };
export const xOf = (s: Scale, t: number) => PAD + (t - s.t0) * s.k;
export const tOf = (s: Scale, x: number) => s.t0 + (x - PAD) / s.k;

/** Rozsah měřítka: od „vše se vejde“ po „15 min přes plátno“; krátký rozsah dat obě meze slije. */
export function zoomLimits(span: number, plotWidth: number): { min: number; max: number } {
  const fit = Math.max(1, plotWidth - 2 * PAD) / Math.max(span, 1);
  const max = Math.max(1, plotWidth) / ZOOM_MAX_SPAN;
  return { min: Math.min(fit, max), max };
}

/**
 * Kolečko: nové `k` (oříznuté do mezí) a `scrollLeft` tak, aby čas pod kurzorem (`cursor` = x ve viewportu plátna)
 * zůstal pod kurzorem.
 */
export function zoomAt(s: Scale, scrollLeft: number, cursor: number, factor: number, limits: { min: number; max: number }): { k: number; scrollLeft: number } {
  const t = tOf(s, scrollLeft + cursor);
  const k = Math.min(limits.max, Math.max(limits.min, s.k * factor));
  return { k, scrollLeft: xOf({ t0: s.t0, k }, t) - cursor };
}

const STEPS = [5, 10, 15, 30, 60, 120, 180, 360, 720, 1440].map((m) => m * MIN);
const TICK_PX = 84;
const two = (n: number) => String(n).padStart(2, "0");

/** Značky osy 5 min … 6 h podle hustoty (nad 6 h ještě 12 h a den, aby dlouhý rozsah nezaplavil hlavičku). */
export function ticks(s: Scale, from: number, to: number): { x: number; text: string }[] {
  const step = STEPS.find((ms) => ms * s.k >= TICK_PX) ?? STEPS[STEPS.length - 1];
  const out: { x: number; text: string }[] = [];
  // zarovnat na místní čas: posun časové zóny, aby 6h značky padly na 0, 6, 12, 18 h
  const offset = new Date(from).getTimezoneOffset() * MIN;
  for (let t = Math.ceil((from - offset) / step) * step + offset; t <= to && out.length < 400; t += step) {
    const d = new Date(t);
    const midnight = d.getHours() === 0 && d.getMinutes() === 0;
    out.push({ x: xOf(s, t), text: midnight ? `${d.getDate()}. ${d.getMonth() + 1}.` : `${two(d.getHours())}:${two(d.getMinutes())}` });
  }
  return out;
}

/** „10,3 h na šířku“ / „45 min na šířku“ pro lištu. */
export function widthText(k: number, plotWidth: number): string {
  const ms = plotWidth / k;
  return ms >= 2 * 60 * MIN ? `${(ms / (60 * MIN)).toFixed(1).replace(".", ",")} h na šířku` : `${Math.round(ms / MIN)} min na šířku`;
}
