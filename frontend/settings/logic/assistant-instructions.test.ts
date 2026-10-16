import { describe, expect, it } from "vitest";
import { INSTRUCTIONS_LIMIT, instructionsPayload, instructionsView, parseAssistantInstructions } from "./assistant-instructions";

const config = { text: "abc", isDefault: true, defaultText: "abc" };

describe("assistant-instructions", () => {
  it("čte jen přesný tvar ze serveru", () => {
    expect(parseAssistantInstructions(config)).toEqual(config);
    expect(parseAssistantInstructions({ text: "a", isDefault: true })).toBeNull();
    expect(parseAssistantInstructions({ text: 1, isDefault: true, defaultText: "" })).toBeNull();
    expect(parseAssistantInstructions(null)).toBeNull();
  });

  it("tělo POST nese text nebo null", () => {
    expect(instructionsPayload("x")).toEqual({ text: "x" });
    expect(instructionsPayload(null)).toEqual({ text: null });
  });

  it("dirty a detail podle uloženého stavu", () => {
    expect(instructionsView(config, "abc")).toMatchObject({ chars: 3, dirty: false, overLimit: false, detail: "Výchozí text z aplikace." });
    expect(instructionsView(config, "abcd").dirty).toBe(true);
    expect(instructionsView({ ...config, isDefault: false }, "abc").detail).toContain("Vlastní text");
    expect(instructionsView(null, "abc").dirty).toBe(false);
  });

  it("hlídá limit znaků", () => {
    expect(instructionsView(config, "x".repeat(INSTRUCTIONS_LIMIT)).overLimit).toBe(false);
    expect(instructionsView(config, "x".repeat(INSTRUCTIONS_LIMIT + 1)).overLimit).toBe(true);
  });
});
