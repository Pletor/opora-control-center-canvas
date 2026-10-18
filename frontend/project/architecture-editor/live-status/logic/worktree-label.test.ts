import { describe, expect, it } from "vitest";
import { shortWorktreeId, worktreeLabel, worktreeName } from "./worktree-label";

const ID = "a0f1764b805144cdbfc18a82f2932e9d";

describe("worktree-label", () => {
  it("vede aktérem a krátkým ID, větev jen v title", () => {
    const label = worktreeLabel({ id: ID, branch: "work/" + ID, actor: "01-start-projektu" });
    expect(label.title).toBe("01-start-projektu");
    expect(label.shortId).toBe("a0f1764b");
    expect(label.tooltip).toBe(`Worktree ${ID} · větev work/${ID} · aktér 01-start-projektu`);
    expect(worktreeName({ id: ID, branch: "work/" + ID, actor: "01-start-projektu" })).toBe("01-start-projektu · a0f1764b");
  });

  it("bez aktéra je hlavním popiskem krátké ID, nikdy celá větev", () => {
    expect(worktreeLabel({ id: ID, branch: "work/" + ID, actor: "" }).title).toBe("a0f1764b");
    expect(worktreeName({ id: ID, branch: "work/" + ID })).toBe("a0f1764b");
  });

  it("bez ID zbude větev", () => {
    expect(worktreeName({ id: "", branch: "work/x" })).toBe("work/x");
    expect(shortWorktreeId("  abc  ")).toBe("abc");
  });
});
