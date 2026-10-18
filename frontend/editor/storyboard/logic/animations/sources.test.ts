import { describe, expect, it } from "vitest";
import { checkExports } from "../code-module";
import { stateAt, validate, type Storyboard } from "../storyboard-model";
import { EMPTY_CODE, EMPTY_SOURCE, codeStoryboard } from "./code";
import { fakeContext } from "./fake-canvas";
import { ANIMATIONS } from "./index";

type Mod = { fields: unknown; layers: { id: string }[]; paint: (...a: unknown[]) => void; defaults?: () => Storyboard };
/** Zdroj modulu v testu: `export` se odstraní a `new Function` vrátí exporty; skutečný import dělá až Worker. */
function compile(source: string): Mod {
  const body = source.replace(/^export\s+/gm, "");
  return new Function(`${body}
return { fields, layers, paint, defaults: typeof defaults === "function" ? defaults : undefined };`)() as Mod;
}

describe("zdroje šablon animací", () => {
  for (const [id, animation] of [...Object.entries(ANIMATIONS), ["kod (prázdná šablona)", { ...EMPTY_CODE, defaults: () => codeStoryboard(EMPTY_CODE) }] as const]) {
    it(`${id}: zdroj se zkompiluje, drží kontrakt a paint nespadne na fake canvasu`, () => {
      const mod = compile(animation.source);
      expect(checkExports(mod as unknown as Record<string, unknown>)).toBeNull();
      expect(mod.layers.map((l) => l.id)).toEqual(animation.layers.map((l) => l.id));
      expect(mod.fields).toEqual(animation.fields);
      const board = animation.defaults();
      const all = new Set(animation.layers.map((l) => l.id));
      for (const t of [0, 1, 2.5, board.duration]) {
        const { ctx, calls } = fakeContext();
        mod.paint(ctx, 192, 108, stateAt(board, {}, t), t, board, all);
        expect(calls.length).toBeGreaterThan(0);
      }
    });
  }
  it("defaults() ze zdroje je platný storyboard", () => {
    for (const a of Object.values(ANIMATIONS)) {
      const board = compile(a.source).defaults!();
      expect(validate({ ...board, animation: "kod", code: { title: "t", source: a.source, fields: a.fields, layers: a.layers } }, ["kod"])).toEqual([]);
    }
  });
  it("kulička ze zdroje kreslí totéž co registrovaná animace", () => {
    const board = ANIMATIONS.kulicka.defaults();
    const mod = compile(ANIMATIONS.kulicka.source);
    const all = new Set(ANIMATIONS.kulicka.layers.map((l) => l.id));
    for (const t of [0.5, 2.3, 3.1, 8]) {
      const a = fakeContext(), b = fakeContext();
      ANIMATIONS.kulicka.paint(a.ctx, 192, 108, stateAt(board, ANIMATIONS.kulicka, t), t, board, all);
      mod.paint(b.ctx, 192, 108, stateAt(board, ANIMATIONS.kulicka, t), t, board, all);
      expect(b.calls).toEqual(a.calls);
    }
  });
  it("prázdná šablona kódu kreslí kruh podle state.x a state.y", () => {
    const { ctx, calls } = fakeContext();
    compile(EMPTY_SOURCE).paint(ctx, 100, 100, { x: 0.25, y: 0.75 }, 0, codeStoryboard(EMPTY_CODE), new Set(["pozadi", "objekt"]));
    expect(calls).toEqual(expect.arrayContaining(["fillRect", "arc", "fill"]));
  });
});
