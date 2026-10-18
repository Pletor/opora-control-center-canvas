// Společné kousky zdrojů šablon: text, který se vkládá do samostatných modulů animací (bez importů).
// Zdroj nesmí obsahovat zpětný apostrof ani `${`, protože leží v šablonovém řetězci.
import type { Field } from "./index";

/** `stateAt(board, t)`: stejná interpolace mezi momenty jako v editoru (čísla a barvy lerp, ostatní drží stav předchozího momentu). */
export const STATE_HELPERS = `const EASES = { linear: (u) => u, in: (u) => u * u, out: (u) => 1 - (1 - u) * (1 - u), inout: (u) => (u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2), hold: () => 0 };
const HEX = /^#[0-9a-f]{6}$/i;
const lerp = (a, b, u) => a + (b - a) * u;
function lerpColor(a, b, u) {
  const ca = parseInt(a.slice(1), 16), cb = parseInt(b.slice(1), 16);
  const ch = (s) => Math.round(lerp((ca >> s) & 255, (cb >> s) & 255, u)).toString(16).padStart(2, "0");
  return "#" + ch(16) + ch(8) + ch(0);
}
export function stateAt(board, t) {
  const ms = board.moments;
  if (!ms.length) return {};
  let i = 0, u = 0;
  if (t > ms[0].t) {
    i = ms.length - 1; u = 1;
    for (let k = 0; k < ms.length - 1; k++) if (t < ms[k + 1].t) { i = k; u = (t - ms[k].t) / (ms[k + 1].t - ms[k].t); break; }
  }
  const a = ms[i], b = ms[i + 1];
  if (!b || u === 0) return { ...a.state };
  const e = (EASES[a.ease] || EASES.linear)(u);
  const out = { ...a.state };
  for (const key of Object.keys(a.state)) {
    const x = a.state[key], y = b.state[key];
    if (typeof x === "number" && typeof y === "number") out[key] = lerp(x, y, e);
    else if (typeof x === "string" && typeof y === "string" && HEX.test(x) && HEX.test(y)) out[key] = lerpColor(x, y, e);
  }
  return out;
}`;

/** Hlavička modulu: exporty `fields`, `layers` a `defaults()` z hodnot šablony. */
export function moduleHead(fields: Field[], layers: { id: string; label: string }[], defaults: unknown): string {
  return `export const fields = ${JSON.stringify(fields)};
export const layers = ${JSON.stringify(layers)};
export function defaults() { return ${JSON.stringify(defaults)}; }`;
}
