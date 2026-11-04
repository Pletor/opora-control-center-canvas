import { hudMotion, type HudPalette, type HudState } from "./hud-palette";

/** Jeden snímek kokpitu: rozměr v CSS px, čas v s, natočení a amplituda (mění je `stepHud`), písmo štítků. */
export type HudFrame = { w: number; h: number; t: number; rot: number; amp: number; font: string };
type Ctx = CanvasRenderingContext2D;

const TAU = Math.PI * 2;
const N_BARS = 96;
const SEEDS = Array.from({ length: N_BARS }, (_, i) => (Math.sin(i * 12.9898) * 43758.5453) % 1);
const rgba = (c: string, a: number) => `rgba(${c},${a})`;

/**
 * Posune natočení a amplitudu o dt (s); bez pohybu (reduced) se otáčí jen nepatrně a vlny stojí nízko.
 * `level` (0–1, P3) je hlasitost mikrofonu při poslechu nebo puls slov při čtení; jádro pak dýchá s hlasem.
 */
export function stepHud(frame: HudFrame, dt: number, state: HudState, reduced: boolean, level: number | null = null): void {
  const motion = hudMotion(state);
  let target = motion.amp;
  if (state === "idle") target += Math.sin(frame.t * 1.1) * 0.04;
  if (level !== null && (state === "listening" || state === "speaking")) target = motion.amp * 0.5 + level * 0.7;
  if (state === "thinking") target = 0.25 + Math.abs(Math.sin(frame.t * 6)) * 0.25;
  if (reduced) target = Math.min(target, 0.1);
  frame.rot += dt * 0.25 * motion.speed * (reduced ? 0.02 : 1);
  frame.amp += (target - frame.amp) * Math.min(1, dt * 6);
}

function ring(ctx: Ctx, cx: number, cy: number, r: number, a0: number, a1: number, w: number, col: string, glow = 0) {
  ctx.beginPath();
  ctx.arc(cx, cy, r, a0, a1);
  ctx.lineWidth = w;
  ctx.strokeStyle = col;
  ctx.shadowBlur = glow;
  ctx.shadowColor = col;
  ctx.stroke();
  ctx.shadowBlur = 0;
}

function ticks(ctx: Ctx, cx: number, cy: number, r: number, n: number, len: number, col: string, every: number, longLen: number, offset: number) {
  ctx.lineWidth = 1;
  ctx.strokeStyle = col;
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const a = offset + (i / n) * TAU;
    const l = i % every === 0 ? longLen : len;
    ctx.moveTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
    ctx.lineTo(cx + Math.cos(a) * (r - l), cy + Math.sin(a) * (r - l));
  }
  ctx.stroke();
}

function bracket(ctx: Ctx, cx: number, cy: number, r: number, a: number, size: number, col: string) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(a);
  ctx.strokeStyle = col;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(r - size, -size);
  ctx.lineTo(r, -size);
  ctx.lineTo(r, size);
  ctx.lineTo(r - size, size);
  ctx.stroke();
  ctx.restore();
}

/** Prstence od kraje ke středu: ticky, štítky stupňů, segmentová hladina, závorky, oblouky, přerušovaný prstenec. */
function drawRings(ctx: Ctx, cx: number, cy: number, R: number, f: HudFrame, p: HudPalette) {
  const { rot, t, amp } = f;
  ctx.strokeStyle = rgba(p.line, 0.08);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx - R * 1.05, cy); ctx.lineTo(cx + R * 1.05, cy);
  ctx.moveTo(cx, cy - R * 1.05); ctx.lineTo(cx, cy + R * 1.05);
  ctx.stroke();

  ring(ctx, cx, cy, R, 0, TAU, 1, rgba(p.line, 0.35));
  ticks(ctx, cx, cy, R, 180, R * 0.02, rgba(p.line, 0.5), 10, R * 0.05, rot * 0.3);
  for (let k = 0; k < 3; k++) {
    const a0 = -rot * 0.6 + k * (TAU / 3);
    ring(ctx, cx, cy, R * 0.955, a0, a0 + (TAU / 3) * 0.55, R * 0.012, rgba(p.line, 0.9), 14);
  }

  ring(ctx, cx, cy, R * 0.84, 0, TAU, 1, rgba(p.line, 0.25));
  ticks(ctx, cx, cy, R * 0.84, 72, R * 0.015, rgba(p.line, 0.5), 6, R * 0.035, rot * 0.5);
  ctx.font = `${Math.max(9, R * 0.035)}px ${f.font}`;
  ctx.fillStyle = rgba(p.line, 0.75);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  // Malé jádro (popup Poslechu) štítky stupňů vynechá, splynuly by do šumu.
  for (let i = 0; R > 120 && i < 12; i++) {
    const a = rot * 0.5 + (i / 12) * TAU;
    ctx.save();
    ctx.translate(cx + Math.cos(a) * R * 0.885, cy + Math.sin(a) * R * 0.885);
    ctx.rotate(a + Math.PI / 2);
    ctx.fillText(String(i * 30).padStart(3, "0"), 0, 0);
    ctx.restore();
  }

  const span = TAU / 36;
  for (let i = 0; i < 36; i++) {
    const level = Math.max(0, Math.sin(t * 2.2 + i * 0.6) * 0.5 + 0.5) * (0.4 + amp * 0.8);
    const a0 = -rot * 0.8 + i * span;
    ctx.globalAlpha = 0.25 + Math.min(1, level) * 0.75;
    ring(ctx, cx, cy, R * 0.72, a0, a0 + span * 0.65, R * 0.03, level > 0.5 ? rgba(p.core, 1) : rgba(p.line, 0.9));
  }
  ctx.globalAlpha = 1;
  ring(ctx, cx, cy, R * 0.69, 0, TAU, 1, rgba(p.line, 0.2));
  ring(ctx, cx, cy, R * 0.75, 0, TAU, 1, rgba(p.line, 0.2));

  for (let k = 0; k < 4; k++) bracket(ctx, cx, cy, R * 0.62, rot * 0.35 + (k * Math.PI) / 2, R * 0.03, rgba(p.line, 0.9));
  ring(ctx, cx, cy, R * 0.6, 0, TAU, 1, rgba(p.line, 0.2));

  for (let k = 0; k < 2; k++) {
    const a0 = -rot * 1.4 + k * Math.PI;
    ring(ctx, cx, cy, R * 0.5, a0, a0 + Math.PI * 0.72, R * 0.018, rgba(p.line, 0.85), 10);
  }
  ctx.setLineDash([R * 0.02, R * 0.03]);
  ctx.lineDashOffset = -rot * R * 0.4;
  ring(ctx, cx, cy, R * 0.44, 0, TAU, 1.5, rgba(p.line, 0.45));
  ctx.setLineDash([]);
}

/** Vlnové čárky kolem jádra, jádro se září, trojice oblouků, tečka uprostřed a skener při přemýšlení. */
function drawCore(ctx: Ctx, cx: number, cy: number, R: number, f: HudFrame, p: HudPalette, state: HudState) {
  const { rot, t, amp } = f;
  const base = R * 0.34;
  ctx.lineWidth = Math.max(1, R * 0.008);
  ctx.lineCap = "round";
  ctx.strokeStyle = rgba(p.core, 0.35 + amp * 0.6);
  ctx.beginPath();
  for (let i = 0; i < N_BARS; i++) {
    const a = (i / N_BARS) * TAU + rot * 0.2;
    const noise = 0.5 + 0.5 * Math.sin(t * 7 + i * 0.9 + SEEDS[i] * 10) * Math.sin(t * 3.1 + i * 0.37);
    const len = R * 0.02 + amp * R * 0.11 * (0.3 + noise);
    ctx.moveTo(cx + Math.cos(a) * base, cy + Math.sin(a) * base);
    ctx.lineTo(cx + Math.cos(a) * (base + len), cy + Math.sin(a) * (base + len));
  }
  ctx.stroke();
  ctx.lineCap = "butt";

  const coreR = R * (0.22 + amp * 0.05);
  const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 1.6);
  glow.addColorStop(0, rgba(p.core, 0.95));
  glow.addColorStop(0.35, rgba(p.line, 0.55 + amp * 0.3));
  glow.addColorStop(0.7, rgba(p.line, 0.12));
  glow.addColorStop(1, rgba(p.line, 0));
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(cx, cy, coreR * 1.6, 0, TAU);
  ctx.fill();
  ring(ctx, cx, cy, coreR, 0, TAU, 2, rgba(p.core, 0.9), 20);
  ring(ctx, cx, cy, coreR * 0.78, 0, TAU, 1, rgba(p.core, 0.5));
  for (let k = 0; k < 3; k++) {
    const a0 = rot * 2.2 + k * (TAU / 3);
    ring(ctx, cx, cy, coreR * 0.62, a0, a0 + (TAU / 3) * 0.6, 3, rgba(p.core, 0.95), 12);
  }
  ctx.fillStyle = rgba(p.core, 0.9);
  ctx.beginPath();
  ctx.arc(cx, cy, Math.max(2, coreR * (0.12 + amp * 0.12)), 0, TAU);
  ctx.fill();

  if (state === "thinking" && typeof ctx.createConicGradient === "function") {
    const sweep = ctx.createConicGradient(rot * 4, cx, cy);
    sweep.addColorStop(0, rgba(p.scan, 0.35));
    sweep.addColorStop(0.15, rgba(p.scan, 0));
    sweep.addColorStop(1, rgba(p.scan, 0));
    ctx.fillStyle = sweep;
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.72, 0, TAU);
    ctx.fill();
  }
}

/** Vykreslí celý kokpit do ctx (transformace na DPR je už nastavená volajícím). */
export function drawHud(ctx: Ctx, frame: HudFrame, palette: HudPalette, state: HudState): void {
  ctx.clearRect(0, 0, frame.w, frame.h);
  const cx = frame.w / 2;
  const cy = frame.h / 2;
  const R = Math.min(frame.w, frame.h) * 0.46;
  if (R <= 0) return;
  drawRings(ctx, cx, cy, R, frame, palette);
  drawCore(ctx, cx, cy, R, frame, palette, state);
}
