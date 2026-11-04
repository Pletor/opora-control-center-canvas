import { describe, expect, it } from "vitest";
import { enterSubmits, promptText, showsEmptyPrompt } from "./empty-prompt";

describe("empty-prompt", () => {
  it("ukáže se jen u prázdného plátna bez přehrávání a kreslení", () => {
    expect(showsEmptyPrompt(0, false, false)).toBe(true);
    expect(showsEmptyPrompt(1, false, false)).toBe(false);
    expect(showsEmptyPrompt(0, true, false)).toBe(false);
    expect(showsEmptyPrompt(0, false, true)).toBe(false);
  });
  it("odešle oříznutý text, prázdný nebo odesílaný ne", () => {
    expect(promptText("  BMI  ", false)).toBe("BMI");
    expect(promptText("   ", false)).toBeNull();
    expect(promptText("BMI", true)).toBeNull();
  });
  it("Enter odešle, Shift+Enter ne", () => {
    expect(enterSubmits({ key: "Enter", shiftKey: false })).toBe(true);
    expect(enterSubmits({ key: "Enter", shiftKey: true })).toBe(false);
    expect(enterSubmits({ key: "Enter", shiftKey: false, isComposing: true })).toBe(false);
    expect(enterSubmits({ key: "a", shiftKey: false })).toBe(false);
  });
});
