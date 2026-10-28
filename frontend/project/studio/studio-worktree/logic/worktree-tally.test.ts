import { describe, expect, it } from "vitest";
import { normalizeWorkStatus } from "@/project/architecture-editor/live-status/logic/live-model";
import type { MapCheckFinding } from "@/project/architecture-editor/domain-map/map-check/logic/map-check";
import type { MapWorktreeOverlay } from "@/project/architecture-editor/domain-map/map-check/logic/map-check-worktrees";
import { holesInWork, sumWorktrees, worktreeBadgeText, worktreeLabel, worktreesByNode } from "./worktree-tally";

const noGoal: MapCheckFinding = { rule: "page.no-goal", nodeId: "home", message: "bez cíle" };
const section: MapCheckFinding = { rule: "section.unrealized", nodeId: "home", solverId: "hero-card", message: "sekce" };
const other: MapCheckFinding = { rule: "page.no-goal", nodeId: "about", message: "bez cíle" };
const overlay: MapWorktreeOverlay = {
  main: [noGoal, section, other],
  worktrees: [
    { workspaceId: "w1", branch: "feat/a", actor: "agent-1", domainId: "web", closed: ["page.no-goal|home||||bez cíle", "neznámý"], opened: [{ rule: "command.no-receiver", nodeId: "btn", solverId: "form", message: "příkaz" }] },
    { workspaceId: "w2", branch: "feat/b", actor: "", domainId: null, closed: ["section.unrealized|home|||hero-card|sekce", "page.no-goal|gone|||gone-card|mimo main"], opened: [] },
    { workspaceId: "w3", branch: "feat/c", actor: "", domainId: null, closed: [], opened: [] },
  ],
};
const locate = (finding: MapCheckFinding) => finding.nodeId;

describe("worktree tally", () => {
  it("marks cards whose holes a worktree closes or opens (solver first), and cards with live work", () => {
    const work = normalizeWorkStatus({
      domains: [{ id: "web", worktrees: [{ id: "w1", branch: "feat/a", actor: "agent-1", sessions: [{ source: "lease", id: "l", state: "active", nodeId: "api" }], cards: [] }] }],
      unassigned: [{ id: "w4", branch: "", sessions: [{ source: "lease", id: "x", state: "expired", nodeId: "gone" }], cards: [{ nodeId: "db" }] }],
    });
    const marks = worktreesByNode(overlay, work, locate);
    expect(Object.fromEntries([...marks].map(([id, list]) => [id, list.map((mark) => mark.workspaceId)])))
      .toEqual({ home: ["w1"], "hero-card": ["w2"], "gone-card": ["w2"], form: ["w1"], api: ["w1"], db: ["w4"] });
    expect(marks.get("db")![0].branch).toBe("w4");
    expect(worktreesByNode(null, null, locate).size).toBe(0);
  });

  it("counts main holes in work where the hole sits", () => {
    const counts = holesInWork(overlay, { findings: [noGoal, section, other] }, locate);
    expect(Object.fromEntries(counts)).toEqual({ home: 2 });
    expect(holesInWork(overlay, null, locate).size).toBe(0);
    expect(holesInWork({ main: [], worktrees: [] }, { findings: [noGoal] }, locate).size).toBe(0);
  });

  it("sums each worktree once and names it", () => {
    const a = { workspaceId: "w1", branch: "feat/a", actor: "agent-1" };
    const b = { workspaceId: "w2", branch: "feat/b", actor: "" };
    const tally = sumWorktrees([[b], undefined, [a, b], null]);
    expect(tally).toEqual({ count: 2, marks: [a, b] });
    expect(worktreeBadgeText(tally!)).toBe("2 worktree");
    expect(worktreeBadgeText(sumWorktrees([[a]])!)).toBe("feat/a");
    expect(worktreeLabel(tally!)).toBe("Ve worktree se pracuje: feat/a (agent-1), feat/b");
    expect(sumWorktrees([[], null])).toBeNull();
  });
});
