// Model storyboardu karty: čisté funkce bez Reactu. Moment je zároveň režijní poznámka a klíčový stav animace;
// jediný zdroj snímku je stateAt(board, animation, t). Žádný časovač, přehrávání řeší rodič.
import type { AnimationDef, Field } from "./animations";

export type StateValue = number | string | boolean;
export type StateRecord = Record<string, StateValue>;
export type Point = { x: number; y: number };
export type Annotation = { kind: "arrow"; from: Point; to: Point; text: string } | { kind: "note"; at: Point; text: string };
export type EaseName = "linear" | "in" | "out" | "inout" | "hold";
/** Skica momentu v Excalidraw: vrstva kresby, PNG export a příznak, že scénu změnil někdo bez exportu. `fileId` je prázdný, když skicu založil agent a PNG ještě nevzniklo (náhled se nekreslí, jen štítek). */
export type MomentSketch = { layer: string; fileId: string; imageStale: boolean };
export type Moment = {
  t: number; title: string; shows: string; changes: string; comment: string;
  /** Agent na komentář odpověděl (v `changes`); člověk při změně komentáře vrací `false`. Chybí-li, štítek „nový komentář“ se nekreslí. */
  answered?: boolean;
  /** Stabilní `m-<8 hex>`; doplňuje backend, frontend ho nevymýšlí. */
  id?: string;
  sketch?: MomentSketch;
  ease: EaseName; state: StateRecord; annotations: Annotation[];
};
/** Vlastní animace z kódu (`animation: "kod"`): samostatný ES modul bez importů a jeho pole a vrstvy. */
export type CodeSpec = {
  source: string; title: string;
  fields: Field[];
  layers: { id: string; label: string }[];
};
export const CODE_ANIMATION = "kod";
export const MAX_CODE_SOURCE = 64000;
/** Webová scéna (`animation: "scena"`): celý HTML dokument přehrávaný v sandboxovaném iframe, řízený `seek(t)`. */
export type SceneSpec = { html: string; title: string; fields: Field[]; layers: { id: string; label: string }[] };
export const SCENE_ANIMATION = "scena";
export const MAX_SCENE_HTML = 262144;
/** Účel podkladu: texture = agent obrázek kreslí (drawImage/createPattern), reference = jen se jím řídí. */
export type AssetPurpose = "texture" | "reference";
/** Co barva znamená: object = barva prvku/objektu, tint = přebarvení textury (multiply přes obrázek). Bez barvy prázdné. */
export type ColorUse = "" | "object" | "tint";
/** Nahraný obrázek (PNG/JPEG/WebP v `drawing_files`) s pokynem člověka: kam a jak ho agent použije. */
export type StoryboardAsset = {
  /** Stabilní `a-<8 hex>`; doplňuje backend. */
  id?: string;
  name: string; fileId: string; mimeType: string; purpose: AssetPurpose;
  /** Id vrstvy animace, prázdné = celá animace. */
  target: string;
  /** Id momentu, prázdné = všechny. */
  momentId: string;
  color: string; colorUse: ColorUse; note: string;
  /** Agent podklad použil; člověk při změně pokynu vrací `false` (backend to vynutí). */
  answered: boolean;
};
export const MAX_ASSETS = 16;
export const ASSET_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;
export const MAX_ASSET_BYTES = 10 * 1024 * 1024;
export type Storyboard = {
  schema: "opora.storyboard/1"; animation: string; title: string; duration: number; fps: number;
  size: { w: number; h: number }; ground: number; background: string; moments: Moment[];
  code?: CodeSpec;
  scene?: SceneSpec;
  assets?: StoryboardAsset[];
  revision?: number; updatedAt?: string;
};

export const SCHEMA = "opora.storyboard/1";
export const EASES: Record<EaseName, (u: number) => number> = {
  linear: (u) => u,
  in: (u) => u * u,
  out: (u) => 1 - (1 - u) * (1 - u),
  inout: (u) => (u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2),
  hold: () => 0,
};
export const EASE_NAMES = Object.keys(EASES) as EaseName[];
export const EASE_LABELS: Record<EaseName, string> = { linear: "lineárně", in: "rozjezd", out: "dojezd", inout: "rozjezd i dojezd", hold: "držet" };

export const MAX_MOMENTS = 200;
export const MAX_ANNOTATIONS = 20;
const HEX = /^#[0-9a-f]{6}$/i;

export const lerp = (a: number, b: number, u: number) => a + (b - a) * u;
export function lerpColor(a: string, b: string, u: number): string {
  const ca = parseInt(a.slice(1), 16), cb = parseInt(b.slice(1), 16);
  const ch = (shift: number) => Math.round(lerp((ca >> shift) & 255, (cb >> shift) & 255, u)).toString(16).padStart(2, "0");
  return "#" + ch(16) + ch(8) + ch(0);
}

/** Výchozí interpolace: čísla lerp, barvy `#rrggbb` lerp, bool a řetězce drží stav předchozího momentu. */
export function interpolateState(a: StateRecord, b: StateRecord, u: number): StateRecord {
  const out: StateRecord = { ...a };
  for (const key of Object.keys(a)) {
    const x = a[key], y = b[key];
    if (typeof x === "number" && typeof y === "number") out[key] = lerp(x, y, u);
    else if (typeof x === "string" && typeof y === "string" && HEX.test(x) && HEX.test(y)) out[key] = lerpColor(x, y, u);
  }
  return out;
}

export function segmentAt(board: Storyboard, t: number): { index: number; u: number } {
  const ms = board.moments;
  if (!ms.length || t <= ms[0].t) return { index: 0, u: 0 };
  for (let i = 0; i < ms.length - 1; i++) {
    if (t < ms[i + 1].t) return { index: i, u: (t - ms[i].t) / (ms[i + 1].t - ms[i].t) };
  }
  return { index: ms.length - 1, u: 1 };
}

/** Stav animace v čase t: mezi momenty a→b podle ease momentu a. */
export function stateAt(board: Storyboard, animation: Pick<AnimationDef, "interpolate">, t: number): StateRecord {
  const ms = board.moments;
  if (!ms.length) return {};
  const { index, u } = segmentAt(board, t);
  const a = ms[index], b = ms[index + 1];
  if (!b || u === 0) return { ...a.state };
  const e = (EASES[a.ease] ?? EASES.linear)(u);
  return (animation.interpolate ?? interpolateState)(a.state, b.state, e);
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const sortedMoments = (ms: Moment[]) => [...ms].sort((a, b) => a.t - b.t);
export const sortMoments = (board: Storyboard): Storyboard => ({ ...board, moments: sortedMoments(board.moments) });
export type Edit = { board: Storyboard; index: number };
function withMoments(board: Storyboard, moments: Moment[], pick: Moment | null): Edit {
  const sorted = sortedMoments(moments);
  return { board: { ...board, moments: sorted }, index: pick ? Math.max(0, sorted.indexOf(pick)) : 0 };
}

export function addMomentAt(board: Storyboard, animation: Pick<AnimationDef, "interpolate">, t: number): Edit {
  if (board.moments.length >= MAX_MOMENTS) return { board, index: board.moments.length - 1 };
  const at = Math.round(clamp(t, 0, board.duration) * 100) / 100;
  const moment: Moment = {
    t: at, title: "Nový moment", shows: "", changes: "", comment: "", ease: "linear",
    state: stateAt(board, animation, at), annotations: [],
  };
  return withMoments(board, [...board.moments, moment], moment);
}

export function duplicateMoment(board: Storyboard, index: number): Edit {
  const src = board.moments[index];
  if (!src || board.moments.length >= MAX_MOMENTS) return { board, index };
  const copy: Moment = {
    ...src, id: undefined, sketch: undefined, t: Math.round(Math.min(board.duration, src.t + 0.5) * 100) / 100, title: src.title + " (kopie)",
    state: { ...src.state }, annotations: src.annotations.map((a) => structuredClone(a)),
  };
  return withMoments(board, [...board.moments, copy], copy);
}

export function removeMoment(board: Storyboard, index: number): Edit {
  if (board.moments.length <= 1 || !board.moments[index]) return { board, index };
  const moments = board.moments.filter((_, i) => i !== index);
  return { board: { ...board, moments }, index: Math.min(index, moments.length - 1) };
}

export function updateMoment(board: Storyboard, index: number, patch: Partial<Moment>): Edit {
  const old = board.moments[index];
  if (!old) return { board, index };
  const next = { ...old, ...patch };
  return withMoments(board, board.moments.map((m, i) => (i === index ? next : m)), next);
}

function withAnnotations(board: Storyboard, momentIndex: number, list: Annotation[]): Storyboard {
  return { ...board, moments: board.moments.map((x, i) => (i === momentIndex ? { ...x, annotations: list } : x)) };
}

/** Index -1 (nebo mimo rozsah) přidá novou anotaci; jinak nahradí existující. */
export function setAnnotation(board: Storyboard, momentIndex: number, annotationIndex: number, annotation: Annotation): Storyboard {
  const m = board.moments[momentIndex];
  if (!m) return board;
  const list = [...m.annotations];
  if (annotationIndex >= 0 && annotationIndex < list.length) list[annotationIndex] = annotation;
  else if (list.length < MAX_ANNOTATIONS) list.push(annotation);
  else return board;
  return withAnnotations(board, momentIndex, list);
}

export function removeAnnotation(board: Storyboard, momentIndex: number, annotationIndex: number): Storyboard {
  const m = board.moments[momentIndex];
  if (!m) return board;
  return withAnnotations(board, momentIndex, m.annotations.filter((_, i) => i !== annotationIndex));
}

const p2 = (p: Point) => `(${p.x.toFixed(2)}, ${p.y.toFixed(2)})`;
export function annotationSentence(a: Annotation): string {
  return a.kind === "arrow" ? `šipka z ${p2(a.from)} do ${p2(a.to)}: ${a.text}` : `poznámka u ${p2(a.at)}: ${a.text}`;
}

/** Pořadí klíčů jako v kontraktu; revize a čas jen když je storyboard má. */
export function serialize(board: Storyboard): Storyboard {
  const moments = board.moments.map((m) => {
    const out: Moment = {
      t: m.t, title: m.title, shows: m.shows, changes: m.changes, comment: m.comment, ease: m.ease,
      state: m.state,
      annotations: m.annotations.map((a): Annotation => a.kind === "arrow"
        ? { kind: "arrow", from: { ...a.from }, to: { ...a.to }, text: a.text }
        : { kind: "note", at: { ...a.at }, text: a.text }),
    };
    if (m.id !== undefined) out.id = m.id;
    if (m.answered !== undefined) out.answered = m.answered;
    if (m.sketch) out.sketch = { layer: m.sketch.layer, fileId: m.sketch.fileId, imageStale: m.sketch.imageStale };
    return out;
  });
  const out: Storyboard = {
    schema: SCHEMA, animation: board.animation, title: board.title, duration: board.duration, fps: board.fps,
    size: { w: board.size.w, h: board.size.h }, ground: board.ground, background: board.background, moments,
  };
  if (board.code) out.code = { source: board.code.source, fields: board.code.fields, layers: board.code.layers, title: board.code.title };
  if (board.scene) out.scene = { title: board.scene.title, html: board.scene.html, fields: board.scene.fields, layers: board.scene.layers };
  if (board.assets) out.assets = board.assets.map((a) => ({ ...(a.id !== undefined ? { id: a.id } : {}), name: a.name, fileId: a.fileId, mimeType: a.mimeType, purpose: a.purpose, target: a.target, momentId: a.momentId, color: a.color, colorUse: a.colorUse, note: a.note, answered: a.answered }));
  if (board.revision !== undefined) out.revision = board.revision;
  if (board.updatedAt !== undefined) out.updatedAt = board.updatedAt;
  return out;
}

/** Stejné meze jako backend (docs/storyboard-karty.md); vrací české chyby, prázdné pole = platné. */
export function validate(board: Storyboard, knownAnimations?: string[]): string[] {
  const errors: string[] = [];
  const range = (v: number, lo: number, hi: number) => Number.isFinite(v) && v >= lo && v <= hi;
  if (knownAnimations && !knownAnimations.includes(board.animation)) errors.push(`Neznámá animace „${board.animation}“.`);
  if (board.animation === CODE_ANIMATION) {
    if (!board.code) errors.push("Chybí kód animace.");
    else if (board.code.source.length > MAX_CODE_SOURCE) errors.push("Kód animace je delší než 64 kB.");
  }
  if (board.animation === SCENE_ANIMATION) {
    if (!board.scene) errors.push("Chybí dokument scény.");
    else if (board.scene.html.length > MAX_SCENE_HTML) errors.push("Dokument scény je delší než 256 kB.");
  }
  if (!range(board.duration, 1, 120)) errors.push("Délka musí být 1–120 s.");
  if (!range(board.fps, 24, 60)) errors.push("Snímková frekvence musí být 24–60.");
  if (!range(board.size.w, 320, 4096) || !range(board.size.h, 320, 4096)) errors.push("Rozměr plátna musí být 320–4096 px.");
  if (board.moments.length < 1 || board.moments.length > MAX_MOMENTS) errors.push("Storyboard musí mít 1–200 momentů.");
  board.moments.forEach((m, i) => {
    const at = `Moment ${i + 1}: `;
    if (!range(m.t, 0, board.duration)) errors.push(at + "čas musí být v rozmezí 0 až délka.");
    for (const key of ["title", "shows", "changes"] as const) if (m[key].length > 500) errors.push(at + `${key} je delší než 500 znaků.`);
    if (m.comment.length > 2000) errors.push(at + "komentář je delší než 2000 znaků.");
    if (!(m.ease in EASES)) errors.push(at + "neznámý ease.");
    const keys = Object.keys(m.state);
    if (keys.length > 32) errors.push(at + "stav má víc než 32 klíčů.");
    for (const k of keys) {
      const v = m.state[k];
      if (typeof v === "number" && !Number.isFinite(v)) errors.push(at + `stav „${k}“ není konečné číslo.`);
      if (typeof v === "string" && v.length > 100) errors.push(at + `stav „${k}“ je delší než 100 znaků.`);
    }
    if (m.annotations.length > MAX_ANNOTATIONS) errors.push(at + "víc než 20 anotací.");
    m.annotations.forEach((a, j) => {
      const pts = a.kind === "arrow" ? [a.from, a.to] : [a.at];
      if (pts.some((p) => !range(p.x, 0, 1) || !range(p.y, 0, 1))) errors.push(at + `anotace ${j + 1} má souřadnice mimo 0–1.`);
      if (a.text.length > 200) errors.push(at + `anotace ${j + 1} má text delší než 200 znaků.`);
    });
  });
  for (let i = 1; i < board.moments.length; i++) if (board.moments[i].t < board.moments[i - 1].t) { errors.push("Momenty nejsou seřazené podle času."); break; }
  const assets = board.assets ?? [];
  if (assets.length > MAX_ASSETS) errors.push("Storyboard smí mít nejvýše 16 podkladů.");
  const momentIds = new Set(board.moments.map((m) => m.id));
  assets.forEach((a, i) => {
    const at = `Podklad ${i + 1}: `;
    if (!a.fileId) errors.push(at + "chybí nahraný obrázek.");
    if (!(ASSET_TYPES as readonly string[]).includes(a.mimeType)) errors.push(at + "jen PNG, JPEG nebo WebP.");
    if (a.color && !HEX.test(a.color)) errors.push(at + "barva musí být #rrggbb.");
    if (a.color && !a.colorUse) errors.push(at + "u barvy vyber, zda je to barva prvku, nebo přebarvení textury.");
    if (a.momentId && !momentIds.has(a.momentId)) errors.push(at + "vybraný moment ve storyboardu není.");
    if (a.note.length > 500) errors.push(at + "pokyn je delší než 500 znaků.");
  });
  return errors;
}

/** Moment se vstupem člověka (komentář, šipky nebo skica), na který agent ještě neodpověděl. */
export const needsAgent = (m: Moment): boolean => m.answered === false && (m.comment.trim() !== "" || m.annotations.length > 0 || !!m.sketch);
export const openComments = (board: Storyboard): number => board.moments.filter(needsAgent).length;
/** Podklady, které agent ještě nepoužil. */
export const openAssets = (board: Storyboard): number => (board.assets ?? []).filter((a) => !a.answered).length;
