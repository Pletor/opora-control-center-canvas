// Animace z kódu (`animation: "kod"`): modul leží ve storyboardu a běží ve Workeru. `codeAnimation` z něj složí obyčejnou
// AnimationDef, aby Stage, náhledy i miniatury nemusely měnit kontrakt: `paint` je synchronní, vykreslí hotový snímek
// z mezipaměti a o chybějící si řekne Workeru; až dorazí, rodič překreslí (hooks.onFrame). Mezipaměť patří objektu board,
// takže po každé úpravě začíná čistá a zastaralé snímky se nikdy nemíchají s novými.
import type { CodeAnimationHost } from "../code-animation-host";
import { CODE_ANIMATION, SCHEMA, type CodeSpec, type Storyboard } from "../storyboard-model";
import type { AnimationDef, Field } from "./index";

export const EMPTY_SOURCE = `export const fields = [
  { key: "x", label: "Poloha x", kind: "number", min: 0, max: 1, step: 0.01 },
  { key: "y", label: "Poloha y", kind: "number", min: 0, max: 1, step: 0.01 },
];
export const layers = [{ id: "pozadi", label: "Pozadí" }, { id: "objekt", label: "Objekt" }];

// paint(ctx, W, H, state, t, board, visible): vykreslí přesně jeden snímek v čase t. state je už zinterpolovaný mezi momenty,
// x a y jsou 0-1 (podíl šířky a výšky). Žádné časovače ani síť; čas bere jen z parametru t.
export function paint(ctx, W, H, state, t, board, visible) {
  if (visible.has("pozadi")) {
    ctx.fillStyle = board.background || "#101418";
    ctx.fillRect(0, 0, W, H);
  }
  if (visible.has("objekt")) {
    ctx.fillStyle = "#f4b942";
    ctx.beginPath();
    ctx.arc(state.x * W, state.y * H, H * 0.05, 0, Math.PI * 2);
    ctx.fill();
  }
}
`;

export const EMPTY_CODE: CodeSpec = {
  title: "Vlastní animace", source: EMPTY_SOURCE,
  fields: [{ key: "x", label: "Poloha x", kind: "number", min: 0, max: 1, step: 0.01 }, { key: "y", label: "Poloha y", kind: "number", min: 0, max: 1, step: 0.01 }],
  layers: [{ id: "pozadi", label: "Pozadí" }, { id: "objekt", label: "Objekt" }],
};

/** Prázdný storyboard 6 s se dvěma momenty; stav vychází z polí (číslo uprostřed rozsahu, barva, text, bool). Sdílí ho kód i scéna. */
export function fieldsStoryboard(animation: string, title: string, fields: Field[]): Storyboard {
  const state = (shift: number) => Object.fromEntries(fields.map((f): [string, number | string | boolean] => [
    f.key,
    f.kind === "number" ? Math.min(f.max ?? 1, Math.max(f.min ?? 0, ((f.min ?? 0) + (f.max ?? 1)) / 2 + shift * ((f.max ?? 1) - (f.min ?? 0)) * 0.2)) : f.kind === "color" ? "#f4b942" : f.kind === "boolean" ? false : "",
  ]));
  const moment = (t: number, title: string, shift: number) => ({ t, title, shows: "", changes: "", comment: "", ease: "inout" as const, state: state(shift), annotations: [] });
  return {
    schema: SCHEMA, animation, title, duration: 6, fps: 60, size: { w: 1920, h: 1080 }, ground: 0.8, background: "#101418",
    moments: [moment(0, "Začátek", -1), moment(6, "Konec", 1)],
  };
}

export const codeStoryboard = (code: CodeSpec): Storyboard => ({ ...fieldsStoryboard(CODE_ANIMATION, code.title, code.fields), code });

type Frames = { ready: Map<string, ImageBitmap>; last: Map<string, ImageBitmap>; pending: Set<string>; failed: Set<string> };
const CACHES = new WeakMap<object, Frames>();
const MAX_FRAMES = 120;
const framesOf = (board: Storyboard): Frames => {
  let frames = CACHES.get(board);
  if (!frames) { frames = { ready: new Map(), last: new Map(), pending: new Set(), failed: new Set() }; CACHES.set(board, frames); }
  return frames;
};

export type CodeHooks = {
  /** Modul je ve Workeru načtený; do té doby se nekreslí nic. */
  ready: boolean;
  /** Otisk obrázků podkladů, které worker má; mění se po každém předání, aby se snímky bez textury nepoužily dál. */
  assetsKey?: string;
  /** Dorazil nový snímek: rodič má překreslit. */
  onFrame: () => void;
  /** Kreslení snímku selhalo; zpráva patří do pásu vrstev. */
  onError: (message: string) => void;
};

export function codeAnimation(code: CodeSpec, host: CodeAnimationHost | null, hooks: CodeHooks): AnimationDef {
  return {
    id: CODE_ANIMATION, label: code.title || "Vlastní kód", fields: code.fields, layers: code.layers, source: code.source,
    defaults: () => codeStoryboard(code),
    paint(ctx, W, H, state, t, board, visible) {
      if (!hooks.ready || !host) return;
      const frames = framesOf(board);
      const layersOn = [...visible].sort();
      const shape = `${W}x${H}|${layersOn.join(",")}|${hooks.assetsKey ?? ""}`;
      const key = `${shape}|${t}|${JSON.stringify(state)}`;
      const bitmap = frames.ready.get(key) ?? frames.last.get(shape);
      if (bitmap) ctx.drawImage(bitmap, 0, 0, W, H);
      if (frames.ready.has(key) || frames.pending.has(key) || frames.failed.has(key)) return;
      frames.pending.add(key);
      // Zdroj kódu Worker už má; nepřenáší se s každým snímkem.
      const lite = { ...board, code: undefined };
      host.paint({ state, t, board: lite, visible: layersOn, width: W, height: H }).then((frame) => {
        frames.pending.delete(key);
        if (!frame) return;
        frames.ready.set(key, frame);
        frames.last.set(shape, frame);
        while (frames.ready.size > MAX_FRAMES) {
          const oldest = frames.ready.keys().next().value as string;
          frames.ready.delete(oldest);
        }
        hooks.onFrame();
      }, (error: Error) => { frames.pending.delete(key); frames.failed.add(key); hooks.onError(error.message); });
    },
  };
}
