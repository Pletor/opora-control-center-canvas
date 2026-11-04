/**
 * Kde stojí plovoucí popup Poslechu: levý horní roh v px okna. Přetažený popup nesmí utéct z obrazovky
 * (ani po zmenšení okna), proto se poloha vždy ořízne na viewport s malým okrajem.
 */

export type Point = { x: number; y: number };
export type Size = { w: number; h: number };

export const POPUP_MARGIN = 12;

/** Výchozí roh: vpravo dole, kde nepřekáží plátnu ani horní liště. */
export function defaultPosition(popup: Size, viewport: Size, margin = POPUP_MARGIN): Point {
  return clampPosition({ x: viewport.w - popup.w - margin, y: viewport.h - popup.h - margin }, popup, viewport, margin);
}

/** Poloha oříznutá tak, aby byl celý popup vidět; větší popup než okno drží levý horní roh. */
export function clampPosition(point: Point, popup: Size, viewport: Size, margin = POPUP_MARGIN): Point {
  const clamp = (value: number, max: number) => Math.max(margin, Math.min(value, Math.max(margin, max - margin)));
  return { x: Math.round(clamp(point.x, viewport.w - popup.w)), y: Math.round(clamp(point.y, viewport.h - popup.h)) };
}
