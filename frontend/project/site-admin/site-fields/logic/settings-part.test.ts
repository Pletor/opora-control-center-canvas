import { expect, it } from "vitest";
import { imageSrc, linkHref, linkProblem, moveAt, readPart, removeAt, replaceAt, urlProblem } from "./settings-part";

it("reads a part against its default shape and keeps free maps", () => {
  const empty = { on: false, port: 587, name: "", items: [] as string[], robots: { index: true }, info: {} as Record<string, unknown> };
  expect(readPart({}, "x", empty)).toEqual(empty);
  const read = readPart({ x: { on: true, port: "25", items: ["a"], robots: { index: false, extra: 1 }, info: { a: { label: "A" } }, gone: 1 } }, "x", empty);
  expect(read).toEqual({ on: true, port: 587, name: "", items: ["a"], robots: { index: false }, info: { a: { label: "A" } } });
});

it("edits lists by index", () => {
  expect(replaceAt(["a", "b"], 1, "c")).toEqual(["a", "c"]);
  expect(removeAt(["a", "b"], 0)).toEqual(["b"]);
  expect(moveAt(["a", "b", "c"], 2, -1)).toEqual(["a", "c", "b"]);
  expect(moveAt(["a", "b"], 0, -1)).toEqual(["a", "b"]);
});

it("checks links like the server", () => {
  expect(linkProblem({ label: "", pageId: "a", url: "" })).toMatch("popisek");
  expect(linkProblem({ label: "A", pageId: "", url: "" })).toMatch("jedno");
  expect(linkProblem({ label: "A", pageId: "a", url: "/a" })).toMatch("jedno");
  expect(linkProblem({ label: "A", pageId: "", url: "javascript:alert(1)" })).toMatch("Odkaz je");
  expect(urlProblem("//evil.example")).not.toBe("");
  expect(linkProblem({ label: "A", pageId: "", url: "mailto:a@b.cz" })).toBe("");
  expect(linkHref({ pageId: "kontakt", url: "" })).toBe("/kontakt");
  expect(linkHref({ pageId: "", url: "" })).toBe("#");
});

it("resolves preview images from assets or https only", () => {
  expect(imageSrc("p1", "assets/Logos/mark.svg")).toBe("/api/site-admin/assets/Logos/mark.svg?project=p1");
  expect(imageSrc("p1", "https://cdn.example/og.png")).toBe("https://cdn.example/og.png");
  expect(imageSrc("p1", "javascript:alert(1)")).toBe("");
});
