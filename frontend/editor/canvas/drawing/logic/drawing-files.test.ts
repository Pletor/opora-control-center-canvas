import { describe, expect, it } from "vitest";
import {
  dropIsBlocked,
  fileIdBatches,
  filesToUpload,
  imageFileIds,
  missingFileIds,
  pasteIsAllowed,
  type DrawingFile,
} from "./drawing-files";

const file = (id: string, mimeType = "image/png"): DrawingFile => ({ id, mimeType, dataURL: `data:${mimeType};base64,AA==`, created: 1 });

describe("imageFileIds", () => {
  it("vrací unikátní fileId nesmazaných obrázků", () => {
    expect(
      imageFileIds([
        { type: "image", fileId: "a" },
        { type: "image", fileId: "a" },
        { type: "image", fileId: "b", isDeleted: true },
        { type: "image", fileId: null },
        { type: "rectangle" },
        { type: "image", fileId: "c" },
      ]),
    ).toEqual(["a", "c"]);
  });
});

describe("missingFileIds a dávky", () => {
  it("vynechá známá ID", () => {
    expect(missingFileIds(["a", "b", "c"], new Set(["b"]))).toEqual(["a", "c"]);
  });
  it("dělí ID na dávky serveru", () => {
    expect(fileIdBatches(["a", "b", "c"], 2)).toEqual([["a", "b"], ["c"]]);
    expect(fileIdBatches([])).toEqual([]);
  });
});

describe("filesToUpload", () => {
  it("nahraje jen dostupné, dosud nepotvrzené a podporované obrázky", () => {
    const result = filesToUpload(["a", "b", "c", "d"], { a: file("a"), b: file("b"), c: file("c", "image/svg+xml") }, new Set(["b"]));
    expect(result.upload.map((f) => f.id)).toEqual(["a"]);
    expect(result.unsupported.map((f) => f.id)).toEqual(["c"]);
  });
});

describe("dropIsBlocked", () => {
  it("pustí obrázky a zablokuje ostatní soubory", () => {
    expect(dropIsBlocked([{ type: "image/png" }, { type: "image/jpeg" }])).toBe(false);
    expect(dropIsBlocked([{ type: "image/png" }, { type: "application/json" }])).toBe(true);
    expect(dropIsBlocked([{ type: "" }])).toBe(true);
  });
});

describe("pasteIsAllowed", () => {
  it("povolí obrázky a běžné prvky", () => {
    expect(pasteIsAllowed({ files: { a: { mimeType: "image/png" } }, elements: [{ type: "image" }, { type: "text" }] })).toBe(true);
    expect(pasteIsAllowed({})).toBe(true);
  });
  it("zablokuje obrázek z URL, nepodporované soubory a webové vložky", () => {
    expect(pasteIsAllowed({ mixedContent: [{ type: "imageUrl" }] })).toBe(false);
    expect(pasteIsAllowed({ files: { a: { mimeType: "application/pdf" } } })).toBe(false);
    for (const type of ["embeddable", "iframe", "magicframe"]) expect(pasteIsAllowed({ elements: [{ type }] })).toBe(false);
  });
});
