// Vrstva šipek a poznámek přes snímek momentu: kreslení na canvas a hledání anotace pod ukazatelem.
// Souřadnice jsou 0–1 vůči plátnu, takže overlay sedí na snímek v jakémkoli rozlišení.
import type { Annotation, Point } from "./storyboard-model";

export const HIT_RADIUS = 0.03;

function distanceToSegment(p: Point, a: Point, b: Point): number {
  const dx = b.x - a.x, dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  const u = len2 === 0 ? 0 : Math.min(1, Math.max(0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2));
  return Math.hypot(p.x - (a.x + u * dx), p.y - (a.y + u * dy));
}

/** Index anotace blízko bodu p (0–1), nejbližší vyhrává; -1 když žádná není v dosahu. */
export function hitAnnotation(annotations: Annotation[], p: Point, aspect = 1): number {
  let best = -1, bestDistance = HIT_RADIUS;
  annotations.forEach((a, i) => {
    const scaled = (q: Point) => ({ x: q.x * aspect, y: q.y });
    const d = a.kind === "arrow" ? distanceToSegment(scaled(p), scaled(a.from), scaled(a.to)) : Math.hypot((p.x - a.at.x) * aspect, p.y - a.at.y);
    if (d <= bestDistance) { best = i; bestDistance = d; }
  });
  return best;
}

function arrow(ctx: CanvasRenderingContext2D, W: number, H: number, from: Point, to: Point, color: string, width: number) {
  const x0 = from.x * W, y0 = from.y * H, x1 = to.x * W, y1 = to.y * H;
  const angle = Math.atan2(y1 - y0, x1 - x0), head = width * 5;
  ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = width;
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x1 - head * Math.cos(angle - 0.4), y1 - head * Math.sin(angle - 0.4));
  ctx.lineTo(x1 - head * Math.cos(angle + 0.4), y1 - head * Math.sin(angle + 0.4));
  ctx.closePath(); ctx.fill();
}

function label(ctx: CanvasRenderingContext2D, W: number, H: number, at: Point, text: string, color: string) {
  if (!text) return;
  const size = Math.max(12, Math.round(H * 0.026));
  ctx.font = `${size}px sans-serif`;
  const w = ctx.measureText(text).width + size;
  const x = Math.min(W - w, Math.max(0, at.x * W)), y = Math.min(H - size * 1.8, Math.max(0, at.y * H));
  ctx.fillStyle = "rgba(15,20,24,0.85)"; ctx.fillRect(x, y, w, size * 1.7);
  ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.strokeRect(x, y, w, size * 1.7);
  ctx.fillStyle = "#e6ebef"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
  ctx.fillText(text, x + size / 2, y + size * 0.85);
}

/** Šipky s hrotem a textem, poznámky jako štítek; vybraná anotace je zvýrazněná, `draft` je rozdělaná šipka. */
export function drawAnnotations(ctx: CanvasRenderingContext2D, W: number, H: number, annotations: Annotation[], selected: number, draft?: { from: Point; to: Point }) {
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  const width = Math.max(2, H * 0.004);
  annotations.forEach((a, i) => {
    const color = i === selected ? "#ffd479" : "#ff7a6b";
    const w = i === selected ? width * 1.6 : width;
    if (a.kind === "arrow") {
      arrow(ctx, W, H, a.from, a.to, color, w);
      label(ctx, W, H, { x: (a.from.x + a.to.x) / 2, y: (a.from.y + a.to.y) / 2 }, a.text, color);
    } else {
      ctx.fillStyle = color; ctx.beginPath(); ctx.arc(a.at.x * W, a.at.y * H, w * 1.8, 0, Math.PI * 2); ctx.fill();
      label(ctx, W, H, { x: a.at.x + 0.01, y: a.at.y + 0.01 }, a.text, color);
    }
  });
  if (draft) arrow(ctx, W, H, draft.from, draft.to, "#ffd479", width);
  ctx.restore();
}
