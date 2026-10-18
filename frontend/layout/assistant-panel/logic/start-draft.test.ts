import { describe, expect, it } from "vitest";
import { applyStartDraft } from "./start-draft";

describe("applyStartDraft", () => {
  it("vloží koncept do prázdného pole", () => {
    expect(applyStartDraft("", "Rozlož sektor")).toBe("Rozlož sektor");
    expect(applyStartDraft(undefined, "Rozlož sektor")).toBe("Rozlož sektor");
    expect(applyStartDraft("  \n", "Rozlož sektor")).toBe("Rozlož sektor");
  });
  it("nepřepíše text, který člověk už napsal", () => {
    expect(applyStartDraft("moje věta", "Rozlož sektor")).toBe("moje věta");
  });
  it("bez konceptu nechá pole být", () => {
    expect(applyStartDraft("abc", undefined)).toBe("abc");
    expect(applyStartDraft("", "  ")).toBe("");
  });
});
