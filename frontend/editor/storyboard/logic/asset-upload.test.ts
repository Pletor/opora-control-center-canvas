import { describe, expect, it } from "vitest";
import { checkAssetFile, newAsset, patchAsset } from "./asset-upload";
import { MAX_ASSET_BYTES, type StoryboardAsset } from "./storyboard-model";

describe("checkAssetFile", () => {
  it("pustí PNG, JPEG i WebP do 10 MB včetně", () => {
    expect(checkAssetFile({ type: "image/png", size: 1000, name: "a.png" })).toBeNull();
    expect(checkAssetFile({ type: "image/jpeg", size: MAX_ASSET_BYTES, name: "a.jpg" })).toBeNull();
    expect(checkAssetFile({ type: "image/webp", size: 1, name: "a.webp" })).toBeNull();
  });
  it("odmítne jiný typ česky", () => {
    expect(checkAssetFile({ type: "image/gif", size: 10, name: "a.gif" })).toBe("Podklad musí být PNG, JPEG nebo WebP.");
    expect(checkAssetFile({ type: "", size: 10, name: "a" })).toBe("Podklad musí být PNG, JPEG nebo WebP.");
  });
  it("odmítne soubor nad 10 MB", () => {
    expect(checkAssetFile({ type: "image/png", size: MAX_ASSET_BYTES + 1, name: "big.png" })).toBe("Podklad je větší než 10 MB.");
  });
});

describe("newAsset", () => {
  it("založí texturu pro celou animaci, bez barvy a pokynu, čekající na agenta", () => {
    expect(newAsset("kámen.png", "abc", "image/png")).toEqual({
      name: "kámen.png", fileId: "abc", mimeType: "image/png", purpose: "texture", target: "", momentId: "",
      color: "", colorUse: "", note: "", answered: false,
    });
  });
});

describe("patchAsset", () => {
  const done: StoryboardAsset = { ...newAsset("a", "f1", "image/png"), answered: true };
  it("vrací nový objekt a původní nemění", () => {
    const next = patchAsset(done, { note: "x" });
    expect(next).not.toBe(done);
    expect(done.note).toBe("");
    expect(done.answered).toBe(true);
  });
  const instruction: [string, Partial<StoryboardAsset>][] = [
    ["fileId", { fileId: "f2" }], ["purpose", { purpose: "reference" }], ["target", { target: "koule" }],
    ["momentId", { momentId: "m-1" }], ["color", { color: "#ff0000" }], ["colorUse", { colorUse: "tint" }], ["note", { note: "obal kouli" }],
  ];
  it.each(instruction)("změna %s vrátí answered na false", (_, patch) => {
    const next = patchAsset(done, patch);
    expect(next.answered).toBe(false);
    expect(next).toMatchObject(patch);
  });
  it("změna jména answered nemění", () => {
    expect(patchAsset(done, { name: "nové" })).toMatchObject({ name: "nové", answered: true });
  });
  it("stejná hodnota answered nemění", () => {
    expect(patchAsset(done, { note: "", purpose: "texture" }).answered).toBe(true);
  });
  it("výslovné answered v patchi platí", () => {
    expect(patchAsset({ ...done, answered: false }, { answered: true }).answered).toBe(true);
  });
});
