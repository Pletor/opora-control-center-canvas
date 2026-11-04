import { expect, it } from "vitest";
import { clip, EMPTY_SEO, hostProblem, pageTitle, readSeo, robotsContent, searchCrumb, structuredDataProblem, structuredDataSample, templateProblem } from "./seo";

it("reads seo with defaults for an older document", () => {
  expect(readSeo({})).toEqual(EMPTY_SEO);
  expect(readSeo({ seo: { titleTemplate: "%s · Ember", robots: { index: false } } }).robots).toEqual({ ...EMPTY_SEO.robots, index: false });
});

it("builds titles, crumbs and clipped text like a search result", () => {
  expect(pageTitle("%s · Ember", "Menu")).toBe("Menu · Ember");
  expect(pageTitle("Ember", "Menu")).toBe("Menu");
  expect(clip("a".repeat(170), 160)).toHaveLength(160);
  expect(clip("krátké", 160)).toBe("krátké");
  expect(searchCrumb("ember.cz", "/menu/kava")).toBe("ember.cz › menu › kava");
});

it("validates template, host and JSON-LD like the server", () => {
  expect(templateProblem("Bez místa")).not.toBe("");
  expect(templateProblem("%s – %s")).not.toBe("");
  expect(templateProblem("%s · Ember")).toBe("");
  expect(hostProblem("https://ember.cz")).not.toBe("");
  expect(hostProblem("www.ember.cz")).toBe("");
  expect(structuredDataProblem("{oops")).toMatch("platný JSON");
  expect(structuredDataProblem("[1]")).toMatch("objekt");
  expect(structuredDataProblem('{"a": "</script>"}')).toMatch("</");
  const sample = structuredDataSample({ ...EMPTY_SEO, siteName: "Ember", canonicalHost: "ember.cz" }, "");
  expect(structuredDataProblem(sample)).toBe("");
  expect(JSON.parse(sample)["@graph"][0].url).toBe("https://ember.cz/");
});

it("writes the robots meta content", () => {
  expect(robotsContent(EMPTY_SEO.robots)).toBe("index, follow, max-image-preview:large, max-snippet:-1");
  expect(robotsContent({ ...EMPTY_SEO.robots, index: false, noarchive: true })).toBe("noindex, follow, noarchive, max-image-preview:large, max-snippet:-1");
});
