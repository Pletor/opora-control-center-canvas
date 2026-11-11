import { describe, expect, it } from "vitest";
import type { MapWorktreeOverlay } from "@/project/architecture-editor/domain-site/map-check/logic/map-check-worktrees";
import { velinWorktrees, worktreeWorkLine } from "./velin-worktrees";

const overlay: MapWorktreeOverlay = {
  main: [],
  worktrees: [
    { workspaceId: "w1", branch: "feat/a", actor: "agent-1", domainId: "web", closed: ["a", "b"], opened: [
      { rule: "command.no-receiver", nodeId: "btn", solverId: "form", message: "Příkaz nikam nevede" },
      { rule: "edge.carries-unset", edgeId: "e1", message: "Vazba bez druhu" },
      { rule: "journey.broken", journeyId: "j", message: "Cesta bez stránky" },
    ] },
    { workspaceId: "w2", branch: "feat/b", actor: "", domainId: null, closed: [], opened: [] },
  ],
};

describe("velín work in worktrees", () => {
  it("lists each worktree with closed count and new holes pointing at the solving card", () => {
    const rows = velinWorktrees(overlay, (finding) => (finding.edgeId === "e1" ? "src" : null), (id) => id.toUpperCase());
    expect(rows.map((row) => [row.branch, row.actor, row.closed, row.opened.length])).toEqual([["feat/a", "agent-1", 2, 3], ["feat/b", "", 0, 0]]);
    expect(rows[0].opened.map((hole) => [hole.nodeId, hole.cardName, hole.ruleLabel])).toEqual([
      ["form", "FORM", "Příkaz nikam nevede"], ["src", "SRC", "Vazba neříká, co nese"], [null, "", "Cesta ztratila stránku"],
    ]);
    expect(rows[0].opened[0].key).toBe("command.no-receiver|btn|||form|Příkaz nikam nevede");
    expect(velinWorktrees(null, () => null, (id) => id)).toEqual([]);
  });

  it("says what the worktree closes and opens in Czech", () => {
    expect(worktreeWorkLine({ closed: 1, opened: [1] })).toBe("zavírá 1 díru · otevírá 1 novou");
    expect(worktreeWorkLine({ closed: 3, opened: [1, 2] })).toBe("zavírá 3 díry · otevírá 2 nové");
    expect(worktreeWorkLine({ closed: 0, opened: [1, 2, 3, 4, 5] })).toBe("zavírá 0 děr · otevírá 5 nových");
  });
});
