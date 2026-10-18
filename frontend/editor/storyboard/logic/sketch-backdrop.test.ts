import { describe, expect, it } from "vitest";
import { backdropElements, isBackdrop, previousSketchFileId, sketchLayer, stripBackdrop, withFreshBackdrop } from "./sketch-backdrop";

describe("backdropElements", () => {
  it("snímek je zamčený a plný, předchozí skica 30 %, oba označené", () => {
    const [frame, prev] = backdropElements({ frameFileId: "f", prevSketchFileId: "p", width: 1920, height: 1080 });
    expect(frame).toMatchObject({ type: "image", fileId: "f", locked: true, opacity: 100, width: 1920, height: 1080, customData: { storyboardBackdrop: true } });
    expect(prev).toMatchObject({ fileId: "p", opacity: 30, locked: true, customData: { storyboardBackdrop: true } });
  });
  it("bez předchozí skici je jen snímek", () => {
    expect(backdropElements({ frameFileId: "f", width: 10, height: 10 })).toHaveLength(1);
    expect(backdropElements({ frameFileId: "f", prevSketchFileId: null, width: 10, height: 10 })).toHaveLength(1);
  });
});

describe("stripBackdrop a withFreshBackdrop", () => {
  const own = { id: "a", customData: { x: 1 } };
  const plain = { id: "b" };
  it("odstraní jen podklad", () => {
    const old = backdropElements({ frameFileId: "old", width: 1, height: 1 });
    expect(stripBackdrop([...old, own, plain])).toEqual([own, plain]);
    expect(old.every(isBackdrop)).toBe(true);
  });
  it("vymění starý podklad za nový a dá ho dolů", () => {
    const old = backdropElements({ frameFileId: "old", prevSketchFileId: "p", width: 1, height: 1 });
    const fresh = backdropElements({ frameFileId: "new", width: 1, height: 1 });
    const out = withFreshBackdrop([own, ...old], fresh);
    expect(out.map((e) => e.id)).toEqual(["sb-backdrop-frame", "a"]);
    expect((out[0] as { fileId: string }).fileId).toBe("new");
  });
});

describe("sketchLayer a previousSketchFileId", () => {
  it("skládá vrstvu z uzlu a momentu", () => expect(sketchLayer("n1", "m-3f9a1c2e")).toBe("sb/n1/m-3f9a1c2e"));
  it("vezme nejbližší předchozí skicu", () => {
    const s = (fileId: string) => ({ sketch: { layer: "l", fileId, imageStale: false } });
    const moments = [s("a"), {}, s("c"), {}, {}];
    expect(previousSketchFileId(moments, 4)).toBe("c");
    expect(previousSketchFileId(moments, 2)).toBe("a");
    expect(previousSketchFileId(moments, 0)).toBeNull();
  });
});
