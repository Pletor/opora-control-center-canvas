import { describe, expect, it } from "vitest";
import { recordsInScope } from "./work-scope";
describe("shared working contexts", () => {
  it("isolates two problems while reusing one explicitly shared source", () => {
    const login = { id: "login-fact", refs: { nodeIds: ["login"] } };
    const tenant = { id: "tenant-fact", refs: { nodeIds: ["tenant"] } };
    const shared = { id: "source", refs: { nodeIds: ["login", "tenant"] } };
    const project = { id: "project-fact", refs: { nodeIds: [] } };
    const records = [login, tenant, shared, project, shared];
    expect(recordsInScope(records, { projectId: "ample", nodeId: "login" })).toEqual([login, shared]);
    expect(recordsInScope(records, { projectId: "ample", nodeId: "tenant" })).toEqual([tenant, shared]);
    expect(recordsInScope(records, { projectId: "ample", nodeId: null })).toEqual([login, tenant, shared, project]);
    expect(recordsInScope(records, { projectId: "ample", nodeId: "login" })[1]).toBe(shared);
    expect(recordsInScope(records, { projectId: "ample", nodeId: "unknown" })).toEqual([]);
    expect(shared.refs.nodeIds).toEqual(["login", "tenant"]);
  });
});
