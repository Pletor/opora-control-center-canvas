// Barevný přechod pozadí tlačítka `{gradient: {angle 0–360, stops: [{color, position 0–1}]}}`, 2–8 zastávek
// (server `buttons.py::_Values.background`). Přepínač „Barevný přechod“ z `image.png` mění barvu na přechod a zpět.
import { cssValue } from "@/project/site-admin/site-fields/logic/field-values";
import type { Background, Gradient } from "./button-model";

export const MAX_STOPS = 8;
export const isGradient = (value: Background | undefined): value is Gradient => typeof value === "object" && value !== null;

/** Zapnutí přechodu začne od současné barvy k tmavšímu zelenému konci (bílý text projde 4,5:1); vypnutí si nechá první barvu. */
export function toggleGradient(value: Background | undefined, on: boolean): Background | undefined {
  if (!on) return isGradient(value) ? value.gradient.stops[0]?.color : value;
  if (isGradient(value)) return value;
  const from = value && value !== "transparent" ? value : "#157a3a";
  return { gradient: { angle: 135, stops: [{ color: from, position: 0 }, { color: "#0a4520", position: 1 }] } };
}

export const withAngle = (value: Gradient, angle: number): Gradient =>
  ({ gradient: { ...value.gradient, angle: Math.min(360, Math.max(0, Math.round(angle))) } });

export function withStop(value: Gradient, index: number, stop: Partial<{ color: string; position: number }>): Gradient {
  const stops = value.gradient.stops.map((item, at) => at === index ? { ...item, ...stop } : item);
  return { gradient: { ...value.gradient, stops: stops.map((item) => ({ ...item, position: Math.min(1, Math.max(0, item.position)) })) } };
}

/** Nová zastávka doprostřed největší mezery. */
export function addStop(value: Gradient): Gradient {
  const stops = [...value.gradient.stops].sort((a, b) => a.position - b.position);
  if (stops.length >= MAX_STOPS) return value;
  let at = 0;
  for (let index = 1; index < stops.length; index++) if (stops[index].position - stops[index - 1].position > stops[at + 1].position - stops[at].position) at = index - 1;
  const position = Math.round(((stops[at].position + stops[at + 1].position) / 2) * 100) / 100;
  stops.splice(at + 1, 0, { color: stops[at].color, position });
  return { gradient: { ...value.gradient, stops } };
}

export const removeStop = (value: Gradient, index: number): Gradient => value.gradient.stops.length <= 2 ? value
  : { gradient: { ...value.gradient, stops: value.gradient.stops.filter((_item, at) => at !== index) } };

/** CSS pozadí jako server: `linear-gradient(<úhel>deg, <barva> <pozice %>, …)`; neplatná barva = žádné pozadí. */
export function backgroundCss(value: Background | undefined): string | null {
  if (!isGradient(value)) return cssValue(value);
  const stops = value.gradient.stops.map((stop) => { const color = cssValue(stop.color); return color && `${color} ${Math.round(stop.position * 1000) / 10}%`; });
  return stops.every(Boolean) ? `linear-gradient(${value.gradient.angle}deg, ${stops.join(", ")})` : null;
}
