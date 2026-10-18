// Kulička: odraz se squashem u země a stretchem ve směru rychlosti. Přenesený prototyp storyboard-kulicka.
import { SCHEMA, stateAt, type Moment, type StateRecord, type Storyboard } from "../storyboard-model";
import type { AnimationDef } from "./index";
import { KULICKA_FIELDS, KULICKA_LAYERS, KULICKA_SOURCE } from "./kulicka.source";

type Row = [t: number, title: string, shows: string, changes: string, x: number, y: number, r: number, color: string, ease: Moment["ease"], contact?: true];
const ROWS: Row[] = [
  [0, "Tečka", "Prázdná tmavá scéna, uprostřed nahoře tečka.", "Tečka se nafoukne do kuličky.", 0.5, 0.2, 0, "#f4b942", "out"],
  [0.6, "Kulička visí", "Kulička plné velikosti visí ve vzduchu, pod ní měkký stín na podlaze.", "Nic – divák si ji prohlédne.", 0.5, 0.2, 0.055, "#f4b942", "hold"],
  [1.5, "Pád", "Kulička se pustí a zrychluje k zemi, protahuje se ve směru pádu.", "Zrychlený pohyb dolů (ease in).", 0.5, 0.2, 0.055, "#f4b942", "in"],
  [2.3, "Dopad 1", "Kulička se na podlaze rozplácne (squash), stín je nejostřejší.", "Odraz vzhůru, lehce doprava.", 0.5, 0.745, 0.055, "#f4b942", "out", true],
  [3.0, "Výskok 1", "Vrchol prvního odrazu, nižší než start.", "Druhý pád.", 0.55, 0.42, 0.055, "#f4b942", "in"],
  [3.7, "Dopad 2", "Menší squash.", "Kratší odraz.", 0.6, 0.745, 0.055, "#f4b942", "out", true],
  [4.2, "Výskok 2", "Nízký vrchol.", "Třetí pád.", 0.64, 0.6, 0.055, "#f4b942", "in"],
  [4.7, "Dopad 3", "Sotva znatelný squash.", "Kulička se už neodrazí, rozjede se po podlaze.", 0.68, 0.745, 0.055, "#f4b942", "linear", true],
  [7.0, "Dojezd", "Kulička dojela k pravému okraji a stojí.", "Odlepí se a pluje do středu, roste a mění barvu.", 0.86, 0.745, 0.055, "#f4b942", "inout"],
  [9.5, "Nádech", "Velká modrá koule uprostřed scény – klidný moment, místo pro titulek.", "Smrskne se zpět do tečky nahoře.", 0.5, 0.45, 0.2, "#4fa3ff", "inout"],
  [12, "Tečka (smyčka)", "Stejný stav jako v čase 0, video smyčkuje.", "—", 0.5, 0.2, 0, "#f4b942", "hold"],
];

/** Squash kolem momentů s contact: zvonová křivka šířky 0,13 s. */
export function squashAt(board: Storyboard, t: number): number {
  let a = 0;
  const w = 0.13;
  for (const m of board.moments) {
    if (m.state.contact !== true) continue;
    const d = Math.abs(t - m.t);
    if (d < w) a = Math.max(a, 0.42 * (1 - d / w) ** 2);
  }
  return a;
}

/** Rychlost v pixelech za sekundu (centrální diference) – zdroj stretche. */
export function velocityAt(board: Storyboard, t: number, W: number, H: number): { vx: number; vy: number } {
  const dt = 1 / 120;
  const a = stateAt(board, {}, t - dt), b = stateAt(board, {}, t + dt);
  return { vx: ((Number(b.x) - Number(a.x)) * W) / (2 * dt), vy: ((Number(b.y) - Number(a.y)) * H) / (2 * dt) };
}

function paint(ctx: CanvasRenderingContext2D, W: number, H: number, s: StateRecord, t: number, board: Storyboard, visible: ReadonlySet<string>) {
  const num = (k: string, d: number) => (typeof s[k] === "number" ? (s[k] as number) : d);
  const x = num("x", 0.5), y = num("y", 0.5), r = num("r", 0.06), opacity = num("opacity", 1);
  const color = typeof s.color === "string" ? s.color : "#f4b942";
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  const gy = (board.ground ?? 0.8) * H;
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
    ctx.fillStyle = `rgba(0,0,0,${shAlpha.toFixed(3)})`;
    ctx.beginPath(); ctx.ellipse(cx, gy, R * (1 + height * 1.6), R * 0.28 * (1 + height * 0.8), 0, 0, Math.PI * 2); ctx.fill();
  }
  if (!visible.has("kulicka")) { ctx.restore(); return; }

  // Deformace: squash u země má přednost, jinak stretch ve směru rychlosti.
  const sq = squashAt(board, t);
  const { vx, vy } = velocityAt(board, t, W, H);
  const st = Math.min(0.32, (Math.hypot(vx, vy) / H) * 0.22) * (1 - sq / 0.42);
  const squashing = sq > st;
  const sx = squashing ? 1 + sq : 1 + st, sy = squashing ? 1 - sq * 0.8 : 1 / (1 + st);
  const rot = squashing ? 0 : Math.atan2(vy, vx);
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

export const kulicka: AnimationDef = {
  id: "kulicka",
  label: "Kulička – odraz",
  layers: KULICKA_LAYERS,
  fields: KULICKA_FIELDS,
  source: KULICKA_SOURCE,
  defaults: () => ({
    schema: SCHEMA, animation: "kulicka", title: "Kulička – odraz, squash a stretch", duration: 12, fps: 60,
    size: { w: 1920, h: 1080 }, ground: 0.8, background: "#101418",
    moments: ROWS.map(([t, title, shows, changes, x, y, r, color, ease, contact]) => ({
      t, title, shows, changes, comment: "", ease,
      state: { x, y, r, color, opacity: 1, contact: contact === true }, annotations: [],
    })),
  }),
  paint,
};
