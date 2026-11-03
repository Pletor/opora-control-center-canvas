import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FlowWorkflow } from "@/shared/flow-editor/logic/flow-types";

const api = vi.fn();
vi.mock("@/shared/types/logic/types", () => ({ api: (...args: unknown[]) => api(...args) }));
const { intentUrls, pickIntentWorkflow, rejectVersion, saveIntentDraft } = await import("./intent-api");

const wf = (id: string, kind: string, owner_ref: string | null): FlowWorkflow => ({ id, kind, project_id: "p", name: id, owner_ref });
const graph = { nodes: [], edges: [] };

describe("page intent API", () => {
  beforeEach(() => api.mockReset());
  it("asks for the page's own page_intent workflow and the page_intent catalog", () => {
    expect(intentUrls.workflows("p", "n1")).toBe("/api/flow/workflows?project=p&kind=page_intent&owner_ref=opora%3Apage%3An1");
    expect(intentUrls.nodeTypes()).toBe("/api/flow/node-types?kind=page_intent");
    expect(pickIntentWorkflow([wf("h", "heart", null), wf("other", "page_intent", "opora:page:n2"), wf("mine", "page_intent", "opora:page:n1")], "n1")?.id).toBe("mine");
    expect(pickIntentWorkflow([wf("h", "heart", "opora:page:n1")], "n1")).toBeNull();
  });
  it("creates the workflow on the first save, then saves the draft into it", async () => {
    api.mockResolvedValueOnce(wf("new", "page_intent", "opora:page:n1")).mockResolvedValueOnce({ id: "v1" });
    await expect(saveIntentDraft(null, "p", "n1", graph, null)).resolves.toEqual({ id: "v1" });
    expect(api.mock.calls[0]).toEqual(["/api/flow/workflows", { kind: "page_intent", name: "Záměr stránky n1", project_id: "p", owner_ref: "opora:page:n1" }]);
    expect(api.mock.calls[1]).toEqual(["/api/flow/workflows/new/versions", { graph, parent_version_id: null }]);
  });
  it("saves straight into an existing workflow and sends the rejection reason trimmed", async () => {
    api.mockResolvedValue({ id: "v2" });
    await saveIntentDraft(wf("w", "page_intent", "opora:page:n1"), "p", "n1", graph, "v1");
    expect(api).toHaveBeenCalledTimes(1);
    await rejectVersion("v2", "  chybí kritérium  ");
    expect(api).toHaveBeenLastCalledWith("/api/flow/versions/v2/reject", { reason: "chybí kritérium" });
  });
});
