import { expect, it } from "vitest";
import type { TypeFamily } from "@/project/site-admin/logic/site-document";
import { addFamily, addGroup, addStyle, fontFromUpload, removeFamily, removeFont, sampleCss, setFamily, styleNames, updateFont } from "./typography";

const type: TypeFamily = {
  fonts: [{ family: "Inter", file: "fonts/inter.woff2", weight: "300 800", style: "normal" }],
  families: { sans: "Inter, system-ui, sans-serif", mono: "ui-monospace, monospace" },
  groups: [{ name: "Text", family: "sans", styles: [{ name: "body", fontSize: "15px", lineHeight: 1.45, fontWeight: 400 }, { name: "code", fontSize: "13px", family: "mono" }] }],
};

it("guesses the font record from the uploaded file name", () => {
  expect(fontFromUpload("Inter-SemiBoldItalic.woff2", "fonts/Inter-SemiBoldItalic.woff2")).toEqual({ family: "Inter", file: "fonts/Inter-SemiBoldItalic.woff2", weight: "600", style: "italic" });
  expect(fontFromUpload("SourceSerif_Variable.ttf", "fonts/x.ttf")).toMatchObject({ family: "Source Serif", weight: "100 900", style: "normal" });
  expect(fontFromUpload("brand.otf", "fonts/brand.otf")).toMatchObject({ family: "brand", weight: "400" });
});

it("renames a family together with the groups and styles that use it, and removes it from them", () => {
  const renamed = setFamily(type, "mono", "code", "Fira Code, monospace");
  expect(renamed.families).toEqual({ sans: type.families.sans, code: "Fira Code, monospace" });
  expect(renamed.groups[0].styles[1].family).toBe("code");
  const removed = removeFamily(type, "sans");
  expect(removed.families).toEqual({ mono: type.families.mono });
  expect(removed.groups[0].family).toBeUndefined();
  expect(addFamily(type, "sans", "x")).toBe(type);
  expect(addFamily(type, "serif", "Georgia, serif").families.serif).toBe("Georgia, serif");
});

it("adds groups and styles with free style names in their own namespace", () => {
  const grouped = addGroup(type, "Headings");
  expect(grouped.groups[1]).toEqual({ name: "Headings", family: "sans", styles: [] });
  const styled = addStyle(addStyle(grouped, 1, "body"), 1, "body");
  expect(styleNames(styled)).toEqual(["body", "code", "body-2", "body-3"]);
});

it("edits and removes font records", () => {
  expect(updateFont(type, 0, { ...type.fonts[0], weight: "400" }).fonts[0].weight).toBe("400");
  expect(removeFont(type, 0).fonts).toEqual([]);
});

it("builds the live sample style from the edited values", () => {
  expect(sampleCss({ name: "display", fontSize: "32", lineHeight: "40", fontWeight: 600, letterSpacing: "-0.01em" }, type.groups[0]))
    .toEqual({ fontFamily: "var(--font-sans)", fontSize: "32px", lineHeight: "40px", fontWeight: "600", letterSpacing: "-0.01em" });
  expect(sampleCss(type.groups[0].styles[1], type.groups[0])).toEqual({ fontFamily: "var(--font-mono)", fontSize: "13px" });
});
