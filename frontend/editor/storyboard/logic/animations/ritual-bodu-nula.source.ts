// Rituál bodu nula jako samostatný ES modul (bez importů) v kontraktu Workeru: fields, layers, defaults, paint.
import type { Field } from "./index";
import { STATE_HELPERS, moduleHead } from "./source-helpers";

export const RITUAL_FIELDS: Field[] = [
  { key: "gather", label: "Sjetí do kruhu", kind: "number", min: 0, max: 1, step: 0.05 },
  { key: "pulse", label: "Rychlost pulzu", kind: "number", min: 0, max: 1, step: 0.05 },
  { key: "found", label: "Nález (blik, rozšíření)", kind: "number", min: 0, max: 1, step: 0.05 },
  { key: "overlay", label: "Průhlednost textu", kind: "number", min: 0, max: 1, step: 0.05 },
  { key: "core", label: "Záře jádra", kind: "number", min: 0, max: 1, step: 0.05 },
  { key: "label", label: "Text překryvu", kind: "string" },
];
export const RITUAL_LAYERS = [{ id: "pozadi", label: "Pozadí" }, { id: "koule", label: "Zlaté koule" }, { id: "jadro", label: "Jádro a kroužky" }, { id: "prekryv", label: "Text překryvu" }];

const moment = (t: number, title: string, gather: number, ease: string) =>
  ({ t, title, shows: "", changes: "", comment: "", ease, state: { gather, pulse: 0.3, found: 0, overlay: 1 - gather, core: 0.5, label: "Bod nula..." }, annotations: [] });
const DEFAULTS = {
  schema: "opora.storyboard/1", animation: "kod", title: "Rituál bodu nula", duration: 4, fps: 60, size: { w: 1920, h: 1080 }, ground: 0.8, background: "#0a0806",
  moments: [moment(0, "Vznášení", 0, "inout"), moment(2, "Kruh", 1, "linear"), moment(4, "Klid", 1, "hold")],
};

export const RITUAL_SOURCE = `${moduleHead(RITUAL_FIELDS, RITUAL_LAYERS, DEFAULTS)}
${STATE_HELPERS}

const ORBS = 8;
const smooth = (u) => u * u * (3 - 2 * u);

// Poloha koule v jednotkách plátna: mezi deterministickým vznášením a kruhem kolem středu.
function orbPosition(i, t, gather, W, H) {
  const free = { x: 0.5 + 0.3 * Math.sin(0.37 * t + i * 1.7), y: 0.5 + 0.3 * Math.cos(0.29 * t + i * 2.3) };
  const angle = (Math.PI * 2 * i) / ORBS - Math.PI / 2;
  const ring = { x: 0.5 + (0.22 * H * Math.cos(angle)) / W, y: 0.5 + 0.22 * Math.sin(angle) };
  const g = smooth(Math.min(1, Math.max(0, gather)));
  return { x: free.x + (ring.x - free.x) * g, y: free.y + (ring.y - free.y) * g };
}

function paintCore(ctx, cx, cy, r0, t, s, H) {
  const flash = s.found * 0.6;
  const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, r0 * (3 + s.core * 3));
  glow.addColorStop(0, "rgba(240,200,90," + Math.min(1, 0.25 + s.core * 0.6 + flash).toFixed(3) + ")");
  glow.addColorStop(1, "rgba(212,166,58,0)");
  ctx.fillStyle = glow;
  ctx.beginPath(); ctx.arc(cx, cy, r0 * (3 + s.core * 3), 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = "rgb(" + Math.round(212 + 43 * flash) + "," + Math.round(166 + 60 * flash) + "," + Math.round(58 + 120 * flash) + ")";
  ctx.beginPath(); ctx.arc(cx, cy, r0, 0, Math.PI * 2); ctx.fill();
  const speed = 0.5 + s.pulse * 3;
  ctx.lineWidth = Math.max(1, H * 0.003);
  for (let k = 0; k < 3; k++) {
    const base = r0 * (1.6 + k * 0.7) * (1 + (s.found * 0.8 * (k + 1)) / 3);
    const radius = base * (1 + 0.08 * (0.2 + s.pulse) * Math.sin(t * speed * Math.PI * 2 + k * 0.9));
    ctx.strokeStyle = "rgba(212,166,58," + (0.7 - k * 0.15).toFixed(2) + ")";
    ctx.beginPath(); ctx.arc(cx, cy, radius, 0, Math.PI * 2); ctx.stroke();
  }
}

export function paint(ctx, W, H, s, t, board, visible) {
  const num = (k) => (typeof s[k] === "number" ? s[k] : 0);
  const gather = num("gather"), overlay = num("overlay");
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  if (visible.has("pozadi")) {
    ctx.fillStyle = board.background || "#0a0806";
    ctx.fillRect(0, 0, W, H);
  }
  for (let i = 0; visible.has("koule") && i < ORBS; i++) {
    const p = orbPosition(i, t, gather, W, H);
    const R = H * 0.07;
    const g = ctx.createRadialGradient(p.x * W, p.y * H, 0, p.x * W, p.y * H, R);
    g.addColorStop(0, "rgba(212,166,58,0.55)");
    g.addColorStop(1, "rgba(212,166,58,0)");
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(p.x * W, p.y * H, R, 0, Math.PI * 2); ctx.fill();
  }
  if (visible.has("jadro")) paintCore(ctx, W / 2, H / 2, H * 0.05, t, { pulse: num("pulse"), found: num("found"), core: num("core") }, H);
  const label = typeof s.label === "string" ? s.label : "";
  if (visible.has("prekryv") && label && overlay > 0) {
    ctx.fillStyle = "rgba(240,225,180," + Math.min(1, overlay).toFixed(3) + ")";
    ctx.font = Math.round(H * 0.045) + "px serif";
    ctx.textAlign = "center";
    ctx.fillText(label, W / 2, H * 0.88);
  }
  ctx.restore();
}
`;
