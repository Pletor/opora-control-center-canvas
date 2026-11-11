import { describe, expect, it } from "vitest";
import type { DesignTokens } from "@/project/site-admin/logic/site-document";
import { mergeDesignTokens } from "./scan-design";

const current: DesignTokens = {
  color: { themes: [{ id: "light", name: "Light" }, { id: "dark", name: "Dark" }], tokens: [
    { name: "primary", value: { light: "#111111", dark: "#eeeeee" } }, { name: "text", value: "#222222" }] },
  type: { fonts: [{ family: "Inter", file: "fonts/inter.woff2", weight: 400, style: "normal" }], families: { body: "Inter, sans-serif" },
    groups: [{ name: "Nadpisy", styles: [{ name: "h1", fontSize: "2rem" }] }] },
  radius: { tokens: [{ name: "r-sm", value: "4px" }] },
};

describe("design ze skenu do Design systému", () => {
  it("slije tokeny podle jména, první téma barvy, písma a styly; nic nemaže", () => {
    const { tokens, changes } = mergeDesignTokens(current, {
      color: { themes: [{ id: "x", name: "X" }], tokens: [{ name: "primary", value: "#ff0000" }, { name: "text", value: "#222222" }, { name: "accent", value: "#00ff00" }] },
      type: { families: { body: "Roboto, sans-serif", heading: "Lora, serif" }, groups: [{ name: "Nadpisy", styles: [{ name: "h1", fontSize: "3rem" }, { name: "h2", fontSize: "2rem" }] }] },
      radius: { tokens: [{ name: "r-sm", value: "6px" }] },
      spacing: { tokens: [{ name: "s-1", value: "8px" }] },
    });
    expect(changes).toEqual([
      { path: "color.primary", before: JSON.stringify({ light: "#111111", dark: "#eeeeee" }), after: JSON.stringify({ light: "#ff0000", dark: "#eeeeee" }) },
      { path: "color.accent", before: null, after: "#00ff00" },
      { path: "type.families.body", before: "Inter, sans-serif", after: "Roboto, sans-serif" },
      { path: "type.families.heading", before: null, after: "Lora, serif" },
      { path: "type.Nadpisy.h1", before: "2rem", after: "3rem" },
      { path: "type.Nadpisy.h2", before: null, after: "2rem" },
      { path: "radius.r-sm", before: "4px", after: "6px" },
      { path: "spacing.s-1", before: null, after: "8px" },
    ]);
    expect(tokens.color.themes).toEqual(current.color.themes);
    expect(tokens.type.fonts).toEqual(current.type.fonts);
    expect(tokens.color.tokens.map((token) => token.name)).toEqual(["primary", "text", "accent"]);
  });
  it("bez návrhu nebo beze změny vrací uložené tokeny", () => {
    expect(mergeDesignTokens(current, null)).toEqual({ tokens: current, changes: [] });
    expect(mergeDesignTokens(current, { color: { tokens: [{ name: "text", value: "#222222" }] }, type: { groups: [{ name: "Nové", styles: [] }] } }).tokens).toBe(current);
    expect(mergeDesignTokens(current, { color: "nic", radius: { tokens: [{ name: "", value: "1px" }, { name: "x" }] } }).changes).toEqual([]);
  });
});
