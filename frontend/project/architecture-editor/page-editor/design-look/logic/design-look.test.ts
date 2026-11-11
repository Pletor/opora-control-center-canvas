import { describe, expect, it } from "vitest";
import type { DesignTokens } from "@/project/site-admin/logic/site-document";
import { designButton, designFonts, designSwatches, lookOf, withLookParam } from "./design-look";

const tokens: DesignTokens = {
  color: { themes: [{ id: "light", name: "Light" }, { id: "dark", name: "Dark" }], tokens: [
    { name: "ink", value: { light: "#111", dark: "#eee" } }, { name: "brand-primary", value: "{ink}" }, { name: "lost", value: "{nikde}" }] },
  type: { fonts: [], families: { body: "Inter, sans-serif", heading: "Lora, serif" }, groups: [] },
  radius: { tokens: [{ name: "r-sm", value: "2px" }, { name: "button", value: "999px" }] },
};

describe("Layout | Design a pruh Design webu", () => {
  it("pohled v adrese: jen look=design, výchozí Layout bez parametru", () => {
    expect(lookOf("?look=design&pageId=p")).toBe("design");
    expect(lookOf("?look=cokoli")).toBe("layout");
    expect(withLookParam("pageId=p&look=design", "layout")).toBe("pageId=p");
    expect(withLookParam("pageId=p", "design")).toBe("pageId=p&look=design");
  });
  it("vzorky v prvním tématu s rozbaleným aliasem, písma a tlačítko", () => {
    expect(designSwatches(tokens)).toEqual([{ name: "ink", color: "#111" }, { name: "brand-primary", color: "#111" }]);
    expect(designFonts(tokens)).toEqual([{ name: "body", stack: "Inter, sans-serif" }, { name: "heading", stack: "Lora, serif" }]);
    expect(designButton(tokens)).toEqual({ background: "#111", color: "#fff", radius: "999px", font: "Inter, sans-serif" });
    const own = { ...tokens, button: { tokens: [{ name: "button-bg", value: "#0a0" }, { name: "button-text", value: "#000" }, { name: "button-radius", value: "4px" }] } };
    expect(designButton(own)).toEqual({ background: "#0a0", color: "#000", radius: "4px", font: "Inter, sans-serif" });
    expect(designButton({ ...tokens, color: { themes: [], tokens: [] } })).toBeNull();
  });
});
