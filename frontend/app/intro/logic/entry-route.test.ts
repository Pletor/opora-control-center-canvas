import { describe, expect, it } from "vitest";
import { ENTRY_LINKS, showsIntro } from "./entry-route";

describe("entry navigation", () => {
  it("opens intro without mounting the project workspace", () => {
    expect(showsIntro("")).toBe(true);
    expect(showsIntro("?screen=intro&project=old")).toBe(true);
  });
  it.each(["?screen=home", "?screen=heart", "?screen=canvas", "?project=one", "?mode=office", "?workspace=main", "?layer=one", "?environment=project", "?env=hub", "?projectView=site"])("preserves existing deep link %s", (search) => {
    expect(showsIntro(search)).toBe(false);
  });
  it("all three entries lead to the existing workspace, with distinct destinations", () => {
    expect(new Set(ENTRY_LINKS.map((entry) => entry.href)).size).toBe(3);
    for (const entry of ENTRY_LINKS) expect(showsIntro(new URL(entry.href, "http://localhost").search)).toBe(false);
  });
});
