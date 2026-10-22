import { describe, expect, it } from "vitest";
import type { AgentAction } from "@/hub/oporahub-agent-state/logic/agent-state";
import { cardGates, parseGates } from "./review-gate";
import { gateView, holdingRule } from "./gate-view";

const exec = "e".repeat(32);
function raw(overrides: Record<string, unknown> = {}, gate: Record<string, unknown> = {}) {
  return { executionId: exec, cardId: "task_a", repository: "o/r", number: 7, headSha: "h".repeat(40), prState: "open",
    reviewJobId: "rj_1", round: 1, riskTier: "medium",
    mergeReadiness: { security: { reviewJobId: "rj_s", phase: "completed", reasons: ["security_path:**/auth/**"], openImportant: 1 },
      selfChecks: { status: "missing", source: null, missing: ["tests"], failed: [], invalid: 0 },
      base: { baseRef: "main", baseSha: "b".repeat(40), mergeBaseSha: "c".repeat(40), behindBy: 3, observedAt: 1, fresh: true },
      template: { missing: ["Risk"] } },
    reviewGate: { status: "blocked", openImportant: 1, requiredHumanApprovals: 2, humanApprovalsAtHead: 1,
      reasons: ["template_incomplete", "stale_against_main", "open_security_findings", "self_checks_missing"],
      humans: { mode: "verified_humans", count: 1, identityIds: ["id_1"], directorId: "id_1", unverifiedApprovals: 2 }, ...gate },
    ...overrides };
}
const action = (verb: string, targetId: string): AgentAction => ({ id: `act_${verb}`, verb, method: "POST", path: "/x", targetId,
  preconditions: {}, status: "ready" });

describe("review gate → card Review step", () => {
  it("parses gates, drops invalid ones and orders open PRs first", () => {
    const gates = parseGates({ items: [raw({ number: 3, prState: "closed" }), raw(), { executionId: 1 }, raw({ cardId: "other" })] });
    expect(gates).toHaveLength(3);
    expect(cardGates(gates, "task_a").map(item => [item.number, item.prState])).toEqual([[7, "open"], [3, "closed"]]);
    expect(() => parseGates({})).toThrow();
  });
  it("names the holding rule by priority, blocking before pending", () => {
    expect(holdingRule(["template_incomplete", "stale_against_main", "open_security_findings"], "blocked")).toBe("open_security_findings");
    expect(holdingRule(["template_incomplete", "stale_against_main"], "pending")).toBe("stale_against_main");
    expect(holdingRule(["x_new"], "pending")).toBe("x_new");
    expect(holdingRule([], "ready")).toBe("");
  });
  it("counts distinct verified humans against required approvals", () => {
    const view = gateView(parseGates({ items: [raw()] })[0], []);
    expect(view).toMatchObject({ status: "blocked", statusGlyph: "✕", rule: "open_security_findings", openImportant: 1,
      approvals: { required: 2, counted: 1, mode: "verified_humans" } });
    expect(view.approvals.notes.join(" ")).toContain("2 schválení z neověřených účtů");
    expect(view.security.state).toBe("blocked");
    expect(view.selfChecks).toMatchObject({ status: "missing", detail: "chybí: tests" });
    expect(view.stale).toMatchObject({ on: true, text: "3 commitů za main" });
    expect(view.template).toMatchObject({ on: true, text: "chybí sekce: Risk" });
  });
  it("falls back to accounts without an identity registry and to 'vypnuto' without security review", () => {
    const view = gateView(parseGates({ items: [raw({ mergeReadiness: { security: null } },
      { status: "ready", reasons: [], humans: undefined, humanApprovalsAtHead: 2 })] })[0], []);
    expect(view).toMatchObject({ rule: "", ruleText: "Brána nic nedrží.", approvals: { counted: 2, mode: "accounts" },
      security: { state: "off", text: "vypnuto" }, selfChecks: { status: "off" }, template: { on: false, text: "pravidlo vypnuto" } });
  });
  it("lists only this gate's agent actions", () => {
    const view = gateView(parseGates({ items: [raw()] })[0], [action("review.self_checks", exec), action("pr.update_branch", exec),
      action("review.claim", "rj_1"), action("review.claim", "rj_other"), action("claim", "task_a")]);
    expect(view.actions.map(item => item.verb)).toEqual(["review.self_checks", "pr.update_branch", "review.claim"]);
  });
});
