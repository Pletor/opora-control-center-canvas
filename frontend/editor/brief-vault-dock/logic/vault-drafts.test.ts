import { describe, expect, it } from "vitest";
import { hasUnsavedDraft, isDraftField, keepVaultMounted, pruneDrafts } from "./vault-drafts";

describe("vault drafts", () => {
  it("counts text fields, not search or switches", () => {
    expect(isDraftField({ tagName: "TEXTAREA" })).toBe(true);
    expect(isDraftField({ tagName: "INPUT", type: "text" })).toBe(true);
    expect(isDraftField({ tagName: "INPUT" })).toBe(true);
    expect(isDraftField({ tagName: "INPUT", type: "search" })).toBe(false);
    expect(isDraftField({ tagName: "INPUT", type: "checkbox" })).toBe(false);
    expect(isDraftField({ tagName: "INPUT", type: "radio" })).toBe(false);
    expect(isDraftField({ tagName: "SELECT" })).toBe(false);
    expect(isDraftField(null)).toBe(false);
  });

  it("is dirty while a written field is still in the vault and not empty", () => {
    const field = (value: string, isConnected = true) => ({ value, isConnected });
    expect(hasUnsavedDraft([])).toBe(false);
    expect(hasUnsavedDraft([field("  "), field("odeslaný formulář", false)])).toBe(false);
    expect(hasUnsavedDraft([field("rozepsaná odpověď")])).toBe(true);
    const fields = new Set([field("text"), field(""), field("pryč", false)]);
    pruneDrafts(fields);
    expect([...fields].map((item) => item.value)).toEqual(["text"]);
  });

  it("keeps the vault mounted (hidden) while a draft waits, even with the panel closed", () => {
    expect(keepVaultMounted(true, false)).toBe(true);
    expect(keepVaultMounted(false, true)).toBe(true);
    expect(keepVaultMounted(false, false)).toBe(false);
  });
});
