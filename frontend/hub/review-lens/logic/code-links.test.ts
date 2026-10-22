import { describe, expect, it } from "vitest";
import { blobUrl, fileLabel, safePath } from "./code-links";

const REPO = { owner: "Pletor", name: "agent-office", host: "github.com" };
const SHA = "373909b753fc26e105264c5f6e35b02afb3e057d";

describe("code links", () => {
  it("accepts only repository-relative POSIX paths", () => {
    expect(safePath("src/a b/c.ts")).toBe("src/a b/c.ts");
    for (const bad of ["/etc/passwd", "C:/x", "a\\b", "../x", "a/../b", "a//b", "./a", "", "a\u0000b", 5]) expect(safePath(bad)).toBeNull();
  });
  it("builds the GitHub blob link from the repo, the head sha and the line range", () => {
    expect(blobUrl(REPO, SHA, { path: "src/a b/c#.ts", startLine: 38, endLine: 85 }))
      .toBe(`https://github.com/Pletor/agent-office/blob/${SHA}/src/a%20b/c%23.ts#L38-L85`);
    expect(blobUrl(REPO, SHA, { path: "src/x.ts", startLine: 7 })).toBe(`https://github.com/Pletor/agent-office/blob/${SHA}/src/x.ts#L7`);
    expect(blobUrl(REPO, SHA, { path: "src/x.ts" })).toBe(`https://github.com/Pletor/agent-office/blob/${SHA}/src/x.ts`);
    // A scheme-looking first segment is still only a path segment under our own origin.
    expect(blobUrl(REPO, SHA, { path: "javascript:alert(1)/x" })).toBe(`https://github.com/Pletor/agent-office/blob/${SHA}/javascript%3Aalert(1)/x`);
  });
  it("gives no link when anything is off", () => {
    expect(blobUrl(REPO, SHA, { path: "../x" })).toBeNull();
    expect(blobUrl(REPO, "abc", { path: "x" })).toBeNull();
    expect(blobUrl(null, SHA, { path: "x" })).toBeNull();
    expect(blobUrl({ ...REPO, host: "evil.example" }, SHA, { path: "x" })).toBeNull();
    expect(blobUrl({ ...REPO, owner: "a/b" }, SHA, { path: "x" })).toBeNull();
  });
  it("labels files with their line range", () => {
    expect(fileLabel({ path: "a.ts", startLine: 3, endLine: 9 })).toBe("a.ts:3–9");
    expect(fileLabel({ path: "a.ts", startLine: 3, endLine: 3 })).toBe("a.ts:3");
    expect(fileLabel({ path: "a.ts" })).toBe("a.ts");
  });
});
