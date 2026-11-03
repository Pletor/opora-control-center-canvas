import { describe, expect, it } from "vitest";
import type { FlowVersion, FlowWorkflow } from "@/shared/flow-editor/logic/flow-types";
import { flowUrls, pickHeartWorkflow, pickVersion } from "./heart-api";

const wf = (id: string, kind: string, project_id: string | null): FlowWorkflow => ({ id, kind, project_id, name: id });
const version = (id: string, n: number, status: FlowVersion["status"]): FlowVersion =>
  ({ id, workflow_id: "w", n, graph: { nodes: [], edges: [] }, hash: "h", parent_version_id: null, status, eval_run_id: null, created_at: "" });

describe("heart canvas API", () => {
  it("prefers the project's own heart over the shared one and ignores other kinds", () => {
    expect(pickHeartWorkflow([wf("page", "page_intent", "p"), wf("shared", "heart", null)], "p")?.id).toBe("shared");
    expect(pickHeartWorkflow([wf("shared", "heart", null), wf("own", "heart", "p")], "p")?.id).toBe("own");
    expect(pickHeartWorkflow([wf("other", "heart", "q")], "p")).toBeNull();
  });
  it("shows the chosen version, otherwise the active one, otherwise the newest", () => {
    const versions = [version("a", 1, "retired"), version("b", 2, "active"), version("c", 3, "draft")];
    expect(pickVersion(versions, "c")?.id).toBe("c");
    expect(pickVersion(versions, null)?.id).toBe("b");
    expect(pickVersion([version("a", 1, "draft"), version("d", 2, "draft")], "nic")?.id).toBe("d");
    expect(pickVersion([], null)).toBeNull();
  });
  it("builds read urls and the candidate write, never an activation", () => {
    expect(flowUrls.workflows("p 1")).toBe("/api/flow/workflows?project=p+1");
    expect(flowUrls.runs("w")).toBe("/api/flow/runs?workflow=w&limit=50");
    expect(flowUrls.log("r")).toBe("/api/flow/runs/r/log?seq=0&limit=2000");
    expect(flowUrls.candidate("v")).toBe("/api/flow/versions/v/candidate");
    expect(Object.values(flowUrls).map((url) => (url as (a: string) => string)("x"))).not.toContain("/api/flow/versions/x/activate");
  });
});
