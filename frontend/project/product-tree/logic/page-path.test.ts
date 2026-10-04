import { describe, expect, it } from "vitest";
import { normalizePagePath, pagePathKey } from "./page-path";

describe("page path draft preflight", () => {
  it("adds only a missing slash and trims draft whitespace", () => {
    expect(normalizePagePath(" kontakt ")).toBe("/kontakt");
    expect(normalizePagePath("kontakt/detail")).toBe("/kontakt/detail");
    for (const path of ["/", "/Login/", "/%6cogin", "/články", "/100%", "/%zz"]) expect(normalizePagePath(path)).toBe(path);
  });
  it.each(["", " ", "https://example.cz/a", "HTTP://example.cz", "mailto:a@b.cz", "//example.cz/a", "/with space", "/a?x=1", "/a#anchor", "/a\\b", "/a//b", "/a/../b", "/./b", "/%2E%2e/b", "/%20", "/%3F", "/%23", "/%5c", "/%00", "/%ff"])("rejects invalid draft %j before a request", (path) => {
    expect(() => normalizePagePath(path)).toThrow();
  });
  it("uses backend codepoint length and checks the added slash too", () => {
    expect(normalizePagePath("a".repeat(2047))).toHaveLength(2048);
    expect(() => normalizePagePath("a".repeat(2048))).toThrow();
    expect(normalizePagePath("/" + "😀".repeat(2047))).toBe("/" + "😀".repeat(2047));
  });
  it("compares decoded paths once, preserving case and existing spelling", () => {
    expect(pagePathKey("/%6cogin/")).toBe(pagePathKey("/login"));
    expect(pagePathKey("/Login")).not.toBe(pagePathKey("/login"));
    expect(pagePathKey("/%252e")).toBe("/%2e");
    expect(pagePathKey("/%zz")).toBe("/%zz");
    expect(pagePathKey("/100%")).toBe("/100%");
    expect(() => pagePathKey("login")).toThrow();
    expect(() => pagePathKey("/a\n")).toThrow();
  });
});
