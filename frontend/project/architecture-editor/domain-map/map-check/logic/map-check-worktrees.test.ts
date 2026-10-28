import { describe, expect, it } from "vitest";
import { findingKey, keyCard, mapWorktreesUrl, normalizeWorktreeOverlay, overlayKey } from "./map-check-worktrees";

describe("map check across worktrees", () => {
  it("builds the address and the finding key like the backend", () => {
    expect(mapWorktreesUrl("p 1")).toBe("/api/project-architecture/map-check/worktrees?project=p+1");
    expect(findingKey({ rule: "page.no-goal", nodeId: "home", message: "bez cíle" })).toBe("page.no-goal|home||||bez cíle");
    expect(findingKey({ rule: "page.no-goal", nodeId: "a", solverId: "a", message: "Stránka nemá cíl (goal)." })).toBe("page.no-goal|a|||a|Stránka nemá cíl (goal).");
    expect(findingKey({ rule: "edge.carries-unset", edgeId: "e1", message: "x" })).toBe("edge.carries-unset||e1|||x");
    expect(keyCard("section.unrealized|home|||hero-card|a|b")).toBe("hero-card");
    expect(keyCard("page.no-goal|home||||bez cíle")).toBe("home");
    expect(keyCard("edge.carries-unset||e1|||x")).toBeUndefined();
  });

  it("reads the overlay defensively", () => {
    const overlay = normalizeWorktreeOverlay({
      main: [{ rule: "page.no-goal", nodeId: "home", message: "bez cíle" }, { rule: "nope", message: "x" }],
      worktrees: [
        { workspaceId: "w1", branch: "feat/a", actor: "agent-1", domainId: "web", closed: ["k", 3, ""], opened: [{ rule: "section.unrealized", nodeId: "home", solverId: "home", message: "sekce" }] },
        { branch: "bez id" },
        { workspaceId: "w2" },
      ],
    });
    expect(overlay.main).toHaveLength(1);
    expect(overlay.worktrees).toEqual([
      { workspaceId: "w1", branch: "feat/a", actor: "agent-1", domainId: "web", closed: ["k"], opened: [{ rule: "section.unrealized", nodeId: "home", solverId: "home", message: "sekce" }] },
      { workspaceId: "w2", branch: "w2", actor: "", domainId: null, closed: [], opened: [] },
    ]);
  });

  it("treats a missing endpoint or garbage as no worktrees", () => {
    for (const raw of [null, undefined, "404", { detail: "Not Found" }, { worktrees: "x" }]) expect(normalizeWorktreeOverlay(raw)).toEqual({ main: [], worktrees: [] });
    expect(overlayKey(null)).toBe("");
    expect(overlayKey({ main: [], worktrees: [] })).toBe("");
  });
});
