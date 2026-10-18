import { describe, expect, it } from "vitest";
import { archiveBlocked, archivedDate, normalizeArchive, reasonProblem, REASON_LIMIT } from "./worktree-archive";

describe("worktree archive", () => {
  it("normalizes the archive list, newest first", () => {
    expect(normalizeArchive(null)).toEqual([]);
    expect(normalizeArchive({ items: [
      { id: "a", nodeId: "d1", branch: "work/a", actor: "x", reason: "nápad nevyšel", archivedAt: "2026-10-01T10:00:00Z" },
      { branch: "bez id" },
      { id: "b", archivedAt: "2026-10-14T10:00:00Z" },
    ] }).map((item) => item.id)).toEqual(["b", "a"]);
  });

  it("requires a short reason", () => {
    expect(reasonProblem("   ")).toContain("nápad nevyšel");
    expect(reasonProblem("x".repeat(REASON_LIMIT + 1))).toContain(String(REASON_LIMIT));
    expect(reasonProblem("nápad nevyšel")).toBe("");
  });

  it("formats the date and keeps unreadable values", () => {
    expect(archivedDate("2026-10-14T08:03:00")).toBe("14. 10. 2026 08:03");
    expect(archivedDate("včera")).toBe("včera");
    expect(archivedDate("")).toBe("");
  });

  it("blocks archiving the worktree the user works in", () => {
    expect(archiveBlocked("w1", "w1")).toContain("přepněte");
    expect(archiveBlocked("w1", "main")).toBe("");
  });
});
