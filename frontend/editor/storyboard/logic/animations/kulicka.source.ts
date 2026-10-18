// Kulička jako samostatný ES modul (bez importů) v kontraktu Workeru: fields, layers, defaults, paint. Zdroj, ze kterého si
// člověk udělá vlastní kód („Použít jako vlastní kód“) a který jde do balíčku pro render jako animation.js.
import type { Field } from "./index";
import { STATE_HELPERS, moduleHead } from "./source-helpers";

export const KULICKA_FIELDS: Field[] = [
  { key: "x", label: "Poloha x", kind: "number", min: 0, max: 1, step: 0.01 },
  { key: "y", label: "Poloha y", kind: "number", min: 0, max: 1, step: 0.01 },
  { key: "r", label: "Poloměr", kind: "number", min: 0, max: 0.5, step: 0.005 },
  { key: "color", label: "Barva", kind: "color" },
  { key: "opacity", label: "Průhlednost", kind: "number", min: 0, max: 1, step: 0.05 },
  { key: "contact", label: "Dotek podlahy (squash)", kind: "boolean" },
];
export const KULICKA_LAYERS = [{ id: "pozadi", label: "Pozadí a podlaha" }, { id: "stin", label: "Stín" }, { id: "kulicka", label: "Kulička" }];

const moment = (t: number, title: string, y: number, ease: string, contact: boolean) =>
  ({ t, title, shows: "", changes: "", comment: "", ease, state: { x: 0.5, y, r: 0.055, color: "#f4b942", opacity: 1, contact }, annotations: [] });
const DEFAULTS = {
  schema: "opora.storyboard/1", animation: "kod", title: "Kulička", duration: 3, fps: 60, size: { w: 1920, h: 1080 }, ground: 0.8, background: "#101418",
  moments: [moment(0, "Pád", 0.2, "in", false), moment(1, "Dopad", 0.745, "out", true), moment(2, "Výskok", 0.35, "in", false), moment(3, "Dopad", 0.745, "hold", true)],
};

export const KULICKA_SOURCE = `${moduleHead(KULICKA_FIELDS, KULICKA_LAYERS, DEFAULTS)}
${STATE_HELPERS}

// Squash kolem momentů s contact: zvonová křivka šířky 0,13 s.
function squashAt(board, t) {
  let a = 0;
  const w = 0.13;
  for (const m of board.moments) {
    if (m.state.contact !== true) continue;
    const d = Math.abs(t - m.t);
    if (d < w) a = Math.max(a, 0.42 * Math.pow(1 - d / w, 2));
  }
  return a;
}

// Rychlost v pixelech za sekundu (centrální diference) – zdroj stretche.
function velocityAt(board, t, W, H) {
  const dt = 1 / 120;
  const a = stateAt(board, t - dt), b = stateAt(board, t + dt);
  return { vx: ((Number(b.x) - Number(a.x)) * W) / (2 * dt), vy: ((Number(b.y) - Number(a.y)) * H) / (2 * dt) };
}

export function paint(ctx, W, H, s, t, board, visible) {
  const num = (k, d) => (typeof s[k] === "number" ? s[k] : d);
  const x = num("x", 0.5), y = num("y", 0.5), r = num("r", 0.06), opacity = num("opacity", 1);
  const color = typeof s.color === "string" ? s.color : "#f4b942";
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  const gy = (board.ground == null ? 0.8 : board.ground) * H;
  if (visible.has("pozadi")) {
    ctx.fillStyle = board.background || "#101418";
    ctx.fillRect(0, 0, W, H);
    const grad = ctx.createLinearGradient(0, gy, 0, H);
    grad.addColorStop(0, "rgba(255,255,255,0.06)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = grad;
    ctx.fillRect(0, gy, W, H - gy);
    ctx.strokeStyle = "rgba(255,255,255,0.18)";
    ctx.lineWidth = Math.max(1, H * 0.002);
    ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(W, gy); ctx.stroke();
  }
  const R = r * H;
  if (R <= 0.01 || opacity <= 0) { ctx.restore(); return; }
  const cx = x * W, cy = y * H;
  // Stín: čím výš kulička, tím větší, slabší a plošší.
  const height = Math.max(0, gy - (cy + R)) / H;
  const shAlpha = Math.max(0, 0.45 - height * 0.6) * opacity;
  if (visible.has("stin")) {
    ctx.fillStyle = "rgba(0,0,0," + shAlpha.toFixed(3) + ")";
    ctx.beginPath(); ctx.ellipse(cx, gy, R * (1 + height * 1.6), R * 0.28 * (1 + height * 0.8), 0, 0, Math.PI * 2); ctx.fill();
  }
  if (!visible.has("kulicka")) { ctx.restore(); return; }
  // Deformace: squash u země má přednost, jinak stretch ve směru rychlosti.
  const sq = squashAt(board, t);
  const v = velocityAt(board, t, W, H);
  const st = Math.min(0.32, (Math.hypot(v.vx, v.vy) / H) * 0.22) * (1 - sq / 0.42);
  const squashing = sq > st;
  const sx = squashing ? 1 + sq : 1 + st, sy = squashing ? 1 - sq * 0.8 : 1 / (1 + st);
  const rot = squashing ? 0 : Math.atan2(v.vy, v.vx);
  const cyAdj = squashing ? cy + R * (1 - sy) : cy; // squash drží spodek kuličky na podlaze
  ctx.globalAlpha = opacity;
  ctx.translate(cx, cyAdj); ctx.rotate(rot); ctx.scale(sx, sy);
  ctx.fillStyle = color;
  ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.fill();
  const g = ctx.createRadialGradient(-R * 0.35, -R * 0.35, R * 0.1, 0, 0, R);
  g.addColorStop(0, "rgba(255,255,255,0.55)");
  g.addColorStop(0.3, "rgba(255,255,255,0)");
  g.addColorStop(1, "rgba(0,0,0,0.35)");
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}
`;
