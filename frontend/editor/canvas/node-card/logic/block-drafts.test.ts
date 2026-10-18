import { afterEach, describe, expect, it } from "vitest";
import { clearDraft, draftKey, draftKeys, hasDrafts, readDraft, writeDraft } from "./block-drafts";

afterEach(() => { for (const key of draftKeys()) clearDraft(key); });

describe("block-drafts", () => {
  it("zapíše a přečte draft nad stejným základem", () => {
    const key = draftKey("n1", "b1", "text");
    writeDraft(key, "uloženo", "rozepsáno");
    expect(readDraft(key, "uloženo")).toBe("rozepsáno");
    expect(draftKeys()).toEqual([key]);
  });

  it("zahodí draft, když se uložený základ změnil", () => {
    const key = draftKey("n1", "b1", "title");
    writeDraft(key, "staré", "rozepsáno");
    expect(readDraft(key, "nové")).toBeUndefined();
    expect(draftKeys()).toEqual([]);
    expect(readDraft(key, "staré")).toBeUndefined();
  });

  it("hodnota shodná se základem draft smaže", () => {
    const key = draftKey("n1", "b1", "text");
    writeDraft(key, "a", "b");
    writeDraft(key, "a", "a");
    expect(draftKeys()).toEqual([]);
  });

  it("clearDraft smaže jen daný klíč", () => {
    writeDraft(draftKey("n1", "b1", "text"), "", "x");
    writeDraft(draftKey("n1", "b2", "port:p1"), "port", "y");
    clearDraft(draftKey("n1", "b1", "text"));
    expect(draftKeys()).toEqual([draftKey("n1", "b2", "port:p1")]);
  });

  it("hasDrafts hlídá kartu podle celého id, ne podle předpony", () => {
    writeDraft(draftKey("n1", "b1", "text"), "", "x");
    expect(hasDrafts("n1")).toBe(true);
    expect(hasDrafts("n")).toBe(false);
    expect(hasDrafts("n10")).toBe(false);
    clearDraft(draftKey("n1", "b1", "text"));
    expect(hasDrafts("n1")).toBe(false);
  });
});
