import { describe, expect, it, vi } from "vitest";
import { adoptionKey, GraphRequests, graphActionPayload, graphPayload, graphProposalStale, graphReadState, newDraftNode, type GraphContext, type GraphProposal } from "./graph-proposals";
import { postGraphProposal } from "./graph-api";

const context: GraphContext = { acceptedHead: null, graphDigest: "digest", graphManifestId: null, readOnly: false, requiresBaseAdoption: true, adoptionDocuments: [] };
const proposal = { id: "proposal", parentRevision: null, graphDigest: "digest", requiresBaseAdoption: true, accepted: false, adoptionDocuments: [] } as unknown as GraphProposal;
describe("graph proposal input and explicit adoption", () => {
  it("can bootstrap a first plan and projects only allowed input fields", () => {
    const node = { ...newDraftNode("task"), name: " Task ", goal: "Goal", id: "forged", x: 500, by: { kind: "human" } };
    expect(graphPayload("p", "w", " First plan ", context, [node], [])).toEqual({ project: "p", workspace: "w", subject: "First plan", parentRevision: null,
      expectedGraphDigest: "digest", plan: { nodes: [{ ref: "task", kind: "node", name: "Task", parent: null,
        spec: { goal: "Goal", non_goals: "", acceptance: "" } }], edges: [] } });
  });
  it("emits local and existing endpoints without embedding stable IDs or source verdicts", () => {
    const node = { ...newDraftNode("task"), name: "Task", parent: "@sector" };
    expect(graphPayload("p", "w", "Next", context, [node], [{ from: "@old", to: "task", carries: "" }]).plan.edges)
      .toEqual([{ from: "@old", to: "task", port: "next" }]);
    expect(graphPayload("p", "w", "Next", context, [node], [{ from: "@old", to: "task", carries: "data" }]).plan.edges)
      .toEqual([{ from: "@old", to: "task", port: "next", carries: "data" }]);
  });
  it("sends explicit valid area dimensions and refuses ambiguous sizes", () => {
    const node = { ...newDraftNode("area"), name: "Area", kind: "area" as const };
    expect(graphPayload("p", "w", "Next", context, [node], []).plan.nodes[0]).toHaveProperty("size", { w: 1200, h: 800 });
    expect(() => graphPayload("p", "w", "Next", context, [{ ...node, width: "1e3" }], [])).toThrow();
  });
  it("rejects missing names, duplicates, unknown endpoints and self references", () => {
    const node = { ...newDraftNode("task"), name: "Task" };
    expect(() => graphPayload("p", "w", "x", context, [newDraftNode("task")], [])).toThrow();
    expect(() => graphPayload("p", "w", "x", context, [node, node], [])).toThrow();
    expect(() => graphPayload("p", "w", "x", context, [node], [{ from: "missing", to: "task", carries: "" }])).toThrow();
    expect(() => graphPayload("p", "w", "x", context, [{ ...node, parent: "task" }], [])).toThrow();
  });
  it("requires acknowledgement bound to this proposal and exact base digest, even on empty Canvas", () => {
    for (const ack of ["", adoptionKey({ ...proposal, id: "another" }), adoptionKey({ ...proposal, graphDigest: "old" })])
      expect(() => graphActionPayload("p", "w", context, proposal, "accept", ack)).toThrow();
    expect(graphActionPayload("p", "w", context, proposal, "accept", adoptionKey(proposal))).toEqual({
      project: "p", workspace: "w", expectedAcceptedHead: null, expectedGraphDigest: "digest", adoptBaseGraphDigest: "digest" });
  });
  it("cannot accept stale context and rebase never sends an adoption acknowledgement", () => {
    const fresh = { ...context, acceptedHead: "new-revision", graphDigest: "fresh" };
    expect(() => graphActionPayload("p", "w", fresh, proposal, "accept", adoptionKey(proposal))).toThrow();
    expect(graphActionPayload("p", "w", fresh, proposal, "rebase", adoptionKey(proposal))).toEqual({
      project: "p", workspace: "w", expectedAcceptedHead: "new-revision", expectedGraphDigest: "fresh" });
  });
  it("later manifests explicitly send null adoption and accepted proposals cannot be repeated", () => {
    expect(graphActionPayload("p", "w", context, { ...proposal, requiresBaseAdoption: false }, "accept", "")).toHaveProperty("adoptBaseGraphDigest", null);
    expect(() => graphActionPayload("p", "w", context, { ...proposal, accepted: true }, "accept", adoptionKey(proposal))).toThrow();
  });
  it("changed adoption documents require explicit rebase even when graph and accepted revision match", () => {
    const changed = { ...context, adoptionDocuments: [{ nodeId: "existing", ownerWorkspace: "w", revision: 1, fields: { goal: "Changed", non_goals: "", acceptance: "" } }] };
    expect(graphProposalStale(changed, proposal)).toBe(true);
    expect(() => graphActionPayload("p", "w", changed, proposal, "accept", adoptionKey(proposal))).toThrow();
    expect(graphActionPayload("p", "w", changed, proposal, "rebase", "")).toHaveProperty("expectedGraphDigest", "digest");
  });
});

describe("request isolation and one-shot mutations", () => {
  it("preserves historical proposals when context fails and disables writes on mismatched reads", () => {
    const history = { status: "fulfilled" as const, value: { items: [proposal], acceptedHead: null } };
    const unavailable = graphReadState({ status: "rejected", reason: new Error("Specifications diverged") }, history);
    expect(unavailable.context).toBeNull(); expect(unavailable.items).toEqual([proposal]); expect(unavailable.error).toContain("diverged");
    const changed = graphReadState({ status: "fulfilled", value: { ...context, acceptedHead: "new" } }, history);
    expect(changed.context).toBeNull(); expect(changed.items).toEqual([proposal]);
  });
  it("scope changes invalidate late reads and action success while preventing duplicate writes", async () => {
    const requests = new GraphRequests();
    const read = requests.next(), action = requests.beginWrite()!;
    expect(read()).toBe(false); expect(requests.beginWrite()).toBeNull();
    let resolve!: () => void;
    const delayed = new Promise<void>(done => { resolve = done; });
    let displayed = "new scope";
    const completion = delayed.then(() => { if (action()) displayed = "old success"; });
    requests.invalidate(); resolve(); await completion;
    expect(displayed).toBe("new scope"); requests.endWrite(); expect(requests.beginWrite()).not.toBeNull();
  });
  it("switching selection invalidates an older detail and acknowledgement generation", () => {
    const requests = new GraphRequests(); const old = requests.next(); requests.invalidate();
    const next = requests.next(); expect(old()).toBe(false); expect(next()).toBe(true);
  });
  it("obtains browser identity before exactly one mutation without forged actor fields", async () => {
    const transport = vi.fn<typeof fetch>().mockResolvedValueOnce(new Response("{}"))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "saved" })));
    expect(await postGraphProposal("/api/oporahub/graph-proposals", { subject: "Task" }, transport)).toEqual({ id: "saved" });
    expect(transport).toHaveBeenCalledTimes(2);
    expect(transport.mock.calls[0][0]).toBe("/api/access/ui-session");
    expect(transport.mock.calls[1][1]?.headers).toEqual({ "Content-Type": "application/json" });
  });
  it.each([403, 428, 409, 503])("never retries a mutation after HTTP %s", async status => {
    const transport = vi.fn<typeof fetch>().mockResolvedValueOnce(new Response("{}"))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: "Refused" }), { status }));
    await expect(postGraphProposal("/api/oporahub/graph-proposals", {}, transport)).rejects.toThrow("Refused");
    expect(transport).toHaveBeenCalledTimes(2);
  });
  it("failed identity prevents any mutation and uncertain delivery is not retried", async () => {
    const denied = vi.fn<typeof fetch>().mockResolvedValue(new Response("{}", { status: 403 }));
    await expect(postGraphProposal("/api/oporahub/graph-proposals", {}, denied)).rejects.toThrow();
    expect(denied).toHaveBeenCalledTimes(1);
    const uncertain = vi.fn<typeof fetch>().mockResolvedValueOnce(new Response("{}")).mockRejectedValueOnce(new Error("network"));
    await expect(postGraphProposal("/api/oporahub/graph-proposals", {}, uncertain)).rejects.toThrow("network");
    expect(uncertain).toHaveBeenCalledTimes(2);
  });
});
