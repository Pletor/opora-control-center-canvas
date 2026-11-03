// Kontrast barev podle WCAG 2.x: relativní jas sRGB a poměr (L1 + 0.05) / (L2 + 0.05). Čte hex a `rgb()`/`hsl()`
// s čísly (formáty, které server přijímá); `oklch()`, `lab()` a další funkce převod nemají, kontrast se u nich
// neukáže. Alfa se ignoruje: token je plná barva podkladu nebo textu.

export type Rgb = [number, number, number];
export type ContrastLevel = "AAA" | "AA" | "fail";

function hex(text: string): Rgb | null {
  const match = text.match(/^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i);
  if (!match) return null;
  const digits = match[1].length <= 4 ? [...match[1]].map((digit) => digit + digit).join("") : match[1];
  return [0, 2, 4].map((at) => parseInt(digits.slice(at, at + 2), 16)) as Rgb;
}

function numbers(args: string): number[] {
  return args.split(/[\s,/]+/).filter(Boolean).map((part) => part.endsWith("%") ? Number(part.slice(0, -1)) / 100 : Number(part));
}

function hsl(h: number, s: number, l: number): Rgb {
  const k = (n: number) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  return [0, 8, 4].map((n) => Math.round(255 * (l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1))))) as Rgb;
}

/** Barva jako sRGB 0–255, nebo `null`, když ji převést neumíme. */
export function parseColor(value: string): Rgb | null {
  const text = value.trim().toLowerCase();
  if (text.startsWith("#")) return hex(text);
  const fn = text.match(/^(rgba?|hsla?)\(([^)]*)\)$/);
  if (!fn) return null;
  const parts = numbers(fn[2]);
  if (parts.length < 3 || parts.some(Number.isNaN)) return null;
  if (fn[1].startsWith("rgb")) {
    const raw = fn[2].split(/[\s,/]+/).filter(Boolean);
    return [0, 1, 2].map((at) => Math.round(raw[at].endsWith("%") ? parts[at] * 255 : parts[at])) as Rgb;
  }
  return hsl(parts[0], parts[1] > 1 ? parts[1] / 100 : parts[1], parts[2] > 1 ? parts[2] / 100 : parts[2]);
}

export function toHex(rgb: Rgb): string {
  return "#" + rgb.map((part) => Math.max(0, Math.min(255, part)).toString(16).padStart(2, "0")).join("");
}

function luminance([r, g, b]: Rgb): number {
  const channel = (value: number) => { const c = value / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** Poměr kontrastu dvou barev (1–21), nebo `null`, když jednu z nich převést neumíme. */
export function contrastRatio(a: string, b: string): number | null {
  const first = parseColor(a), second = parseColor(b);
  if (!first || !second) return null;
  const [light, dark] = [luminance(first), luminance(second)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

/** Úroveň pro běžný text: AAA od 7:1, AA od 4.5:1, jinak nevyhovuje. */
export function contrastLevel(ratio: number): ContrastLevel {
  return ratio >= 7 ? "AAA" : ratio >= 4.5 ? "AA" : "fail";
}
