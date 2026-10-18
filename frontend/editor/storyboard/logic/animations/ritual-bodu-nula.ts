// Rituál bodu nula (Tajemství Opory): čekací animace věštby jako funkce času. Osm zlatých koulí se ze
// vznášení sjede do kruhu, jádro se třemi kroužky pulzuje a při nálezu zableskne. Originál (CSS keyframes
// a setTimeout) se nekopíruje; tohle je jeho storyboardová podoba, kde čas řídí zvenčí t.
import { SCHEMA, type Moment, type StateRecord, type Storyboard } from "../storyboard-model";
import type { AnimationDef } from "./index";
import { RITUAL_FIELDS, RITUAL_LAYERS, RITUAL_SOURCE } from "./ritual-bodu-nula.source";

const ORBS = 8;
const smooth = (u: number) => u * u * (3 - 2 * u);

/** Poloha koule i v normalizovaných jednotkách plátna: mezi deterministickým vznášením a kruhem kolem středu. */
export function orbPosition(i: number, t: number, gather: number, W: number, H: number): { x: number; y: number } {
  const free = { x: 0.5 + 0.3 * Math.sin(0.37 * t + i * 1.7), y: 0.5 + 0.3 * Math.cos(0.29 * t + i * 2.3) };
  const angle = (Math.PI * 2 * i) / ORBS - Math.PI / 2;
  const ring = { x: 0.5 + (0.22 * H * Math.cos(angle)) / W, y: 0.5 + 0.22 * Math.sin(angle) };
  const g = smooth(Math.min(1, Math.max(0, gather)));
  return { x: free.x + (ring.x - free.x) * g, y: free.y + (ring.y - free.y) * g };
}

function paint(ctx: CanvasRenderingContext2D, W: number, H: number, s: StateRecord, t: number, board: Storyboard, visible: ReadonlySet<string>) {
  const num = (k: string) => (typeof s[k] === "number" ? (s[k] as number) : 0);
  const gather = num("gather"), pulse = num("pulse"), found = num("found"), overlay = num("overlay"), core = num("core");
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

  if (visible.has("jadro")) paintCore(ctx, W / 2, H / 2, H * 0.05, t, { pulse, found, core }, H);
  const label = typeof s.label === "string" ? s.label : "";
  if (visible.has("prekryv") && label && overlay > 0) {
    ctx.fillStyle = `rgba(240,225,180,${Math.min(1, overlay).toFixed(3)})`;
    ctx.font = `${Math.round(H * 0.045)}px serif`;
    ctx.textAlign = "center";
    ctx.fillText(label, W / 2, H * 0.88);
  }
  ctx.restore();
}

function paintCore(ctx: CanvasRenderingContext2D, cx: number, cy: number, r0: number, t: number, s: { pulse: number; found: number; core: number }, H: number) {
  const { pulse, found, core } = s;
  const flash = found * 0.6;
  const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, r0 * (3 + core * 3));
  glow.addColorStop(0, `rgba(240,200,90,${Math.min(1, 0.25 + core * 0.6 + flash).toFixed(3)})`);
  glow.addColorStop(1, "rgba(212,166,58,0)");
  ctx.fillStyle = glow;
  ctx.beginPath(); ctx.arc(cx, cy, r0 * (3 + core * 3), 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = `rgb(${Math.round(212 + 43 * flash)},${Math.round(166 + 60 * flash)},${Math.round(58 + 120 * flash)})`;
  ctx.beginPath(); ctx.arc(cx, cy, r0, 0, Math.PI * 2); ctx.fill();

  const speed = 0.5 + pulse * 3;
  ctx.lineWidth = Math.max(1, H * 0.003);
  for (let k = 0; k < 3; k++) {
    const base = r0 * (1.6 + k * 0.7) * (1 + found * 0.8 * (k + 1) / 3);
    const radius = base * (1 + 0.08 * (0.2 + pulse) * Math.sin(t * speed * Math.PI * 2 + k * 0.9));
    ctx.strokeStyle = `rgba(212,166,58,${(0.7 - k * 0.15).toFixed(2)})`;
    ctx.beginPath(); ctx.arc(cx, cy, radius, 0, Math.PI * 2); ctx.stroke();
  }
}

const m = (t: number, title: string, shows: string, changes: string, ease: Moment["ease"], state: Record<string, number | string>): Moment =>
  ({ t, title, shows, changes, comment: "", ease, state: { gather: 0, pulse: 0.3, found: 0, overlay: 1, core: 0.4, label: "Bod nula...", ...state }, annotations: [] });

export const ritualBoduNula: AnimationDef = {
  id: "ritual-bodu-nula",
  label: "Rituál bodu nula",
  layers: RITUAL_LAYERS,
  fields: RITUAL_FIELDS,
  source: RITUAL_SOURCE,
  defaults: () => ({
    schema: SCHEMA, animation: "ritual-bodu-nula", title: "Rituál bodu nula – čekání na věštbu", duration: 6, fps: 60,
    size: { w: 1920, h: 1080 }, ground: 0.8, background: "#0a0806",
    moments: [
      m(0, "Vznášení", "Osm zlatých koulí se volně vznáší, uprostřed jádro, nahoře text „Bod nula...“.", "Nic – divák vstoupí do scény.", "linear", {}),
      m(0.3, "Začátek sjetí", "Koule se začínají stahovat ke středu, text se změní na „Propojování...“.", "Koule plynule sjíždějí do kruhu.", "inout", { label: "Propojování..." }),
      m(2, "Kruh hotový", "Koule tvoří kruh kolem jádra, text mizí.", "Jádro se připraví na nález.", "linear", { gather: 1, pulse: 0.5, overlay: 0, core: 0.6, label: "Propojování..." }),
      m(3, "Nález", "Jádro bliká a kroužky se rozšíří.", "Blik odeznívá, kroužky se uklidní.", "out", { gather: 1, pulse: 0.8, found: 1, overlay: 0, core: 1, label: "Propojování..." }),
      m(4, "Výsledek", "Klidný kruh, jádro svítí, kroužky pomalu pulzují.", "Nic – výsledek zůstane na scéně.", "linear", { gather: 1, pulse: 0.2, overlay: 0, core: 0.7, label: "Propojování..." }),
      m(6, "Klid (smyčka)", "Stejný stav jako ve 4 s, scéna se dá zasmyčkovat.", "—", "hold", { gather: 1, pulse: 0.2, overlay: 0, core: 0.7, label: "Propojování..." }),
    ],
  }),
  paint,
};
