import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CanvasNode } from "@/shared/types/logic/types";
import { editableNodes, graphEditPayload, nodeEdit } from "./graph-edits";
import { adoptionKey, graphActionPayload, graphProposalStale, type GraphContext, type GraphProposal } from "./graph-proposals";
import GraphChangeReview from "../components/GraphChangeReview";
import GraphProposalDetails from "../components/GraphProposalDetails";
import type { GraphProposalsView } from "./use-graph-proposals";

const node: CanvasNode = { id: "n", kind: "node", name: "Accepted", purpose: "accepted purpose", parentId: null, x: 1, y: 2 };
const context: GraphContext = { acceptedHead: "head", graphDigest: "digest", graphManifestId: "manifest", readOnly: false,
  requiresBaseAdoption: false, adoptionDocuments: [], acceptedGraph: { nodes: [node], edges: [] },
  workingGraph: { nodes: [{ ...node, name: "Working", purpose: "unaccepted drift", x: 900 }], edges: [] } };
const draft = () => ({ nodes: [{ ...nodeEdit(context.workingGraph!.nodes[0]), selected: ["name"] as ("name" | "purpose" | "sourceRef" | "parentId" | "x" | "y" | "size")[], name: "Renamed" }], edges: [] });
const payload = (value = draft(), current = context) => graphEditPayload("p", "w", "Reason", current, value);
const proposal = { id: "proposal", schemaVersion: 2, kind: "graph-changes", parentRevision: "head", graphDigest: "digest", accepted: false,
  requiresBaseAdoption: false, subject: "Edits", by: { name: "human", kind: "human" }, createdAt: "2026-01-01", refs: {}, inside: {},
  additions: { nodes: [], edges: [] }, specifications: [], baseGraph: context.workingGraph,
  changes: { nodes: [{ id: "n", operation: "update", fields: ["name"], acceptedBefore: node, workingBefore: context.workingGraph!.nodes[0],
    proposedAccepted: { ...node, name: "Renamed" }, proposedWorking: { ...context.workingGraph!.nodes[0], name: "Renamed" } }], edges: [], areaMembership: [] },
  stateEffects: { revision: 1, affectedDigest: "state", before: {}, after: {}, effects: { removedNodes: {}, unassignedTickets: [] } } } as unknown as GraphProposal;

describe("explicit graph edit projection", () => {
  it("only sends chosen fields, never unrelated working drift or derived evidence", () => {
    expect(payload()).toEqual({ project: "p", workspace: "w", subject: "Reason", parentRevision: "head", expectedGraphDigest: "digest",
      plan: { updateNodes: [{ id: "n", fields: { name: "Renamed" } }], removeNodes: [], updateEdges: [], removeEdges: [] } });
  });
  it("supports explicit null clears and independently selected coordinates", () => {
    const value = draft(); value.nodes[0].selected = ["sourceRef", "parentId", "y"];
    expect(payload(value).plan.updateNodes[0].fields).toEqual({ sourceRef: null, parentId: null, y: 2 });
  });
  it("does not silently remove closure nodes or edges", () => {
    const value = draft(); value.nodes[0].remove = true;
    expect(payload(value).plan).toEqual({ updateNodes: [], removeNodes: ["n"], updateEdges: [], removeEdges: [] });
  });
  it("projects edge updates using server IDs and source/target, rejecting unsupported ports", () => {
    const other = { ...node, id: "other" };
    const edge = { id: "edge", source: "n", target: "other", port: "next" as const };
    const current = { ...context, acceptedGraph: { nodes: [node, other], edges: [edge] }, workingGraph: { nodes: [node, other], edges: [edge] } };
    const result = graphEditPayload("p", "w", "Rewire", current, { nodes: [], edges: [{ id: "edge", remove: false, source: "other", target: "n" }] });
    expect(result.plan.updateEdges).toEqual([{ id: "edge", source: "other", target: "n", port: "next" }]);
    const blocked = { ...current, acceptedGraph: { ...current.acceptedGraph, edges: [{ ...edge, port: "block" as const }] }, workingGraph: { ...current.workingGraph, edges: [{ ...edge, port: "block" as const }] } };
    expect(() => graphEditPayload("p", "w", "Remove", blocked, { nodes: [], edges: [{ id: "edge", remove: true, source: "n", target: "other" }] })).toThrow();
  });
  it("only imports architecture dependency context after explicit selection and observed drift", () => {
    const current = { ...context, architectureContext: { accepted: context.acceptedGraph!, working: context.workingGraph!, differs: true } };
    expect(payload(draft(), current).plan).not.toHaveProperty("adoptArchitectureContext");
    const result = graphEditPayload("p", "w", "Adopt dependency", current, { nodes: [], edges: [], adoptArchitectureContext: true });
    expect(result.plan).toEqual({ updateNodes: [], removeNodes: [], updateEdges: [], removeEdges: [], adoptArchitectureContext: true });
    expect(() => graphEditPayload("p", "w", "Adopt", context, { nodes: [], edges: [], adoptArchitectureContext: true })).toThrow();
  });
  it("retains accepted-only nodes for explicit removal but rejects updates to missing working nodes", () => {
    const current = { ...context, workingGraph: { nodes: [], edges: [] } };
    expect(editableNodes(current).map(item => item.id)).toEqual(["n"]);
    expect(() => payload(draft(), current)).toThrow();
    const value = draft(); value.nodes[0].remove = true; expect(payload(value, current).plan.removeNodes).toEqual(["n"]);
  });
  it("rejects missing manifest, duplicate operations, unknown IDs, empty chosen fields and invalid coordinates", () => {
    expect(() => payload(draft(), { ...context, graphManifestId: null })).toThrow();
    const duplicate = draft(); duplicate.nodes.push(duplicate.nodes[0]); expect(() => payload(duplicate)).toThrow();
    const unknown = draft(); unknown.nodes[0].id = "unknown"; expect(() => payload(unknown)).toThrow();
    const empty = draft(); empty.nodes[0].selected = []; expect(() => payload(empty)).toThrow();
    const invalid = draft(); invalid.nodes[0].selected = ["x"]; invalid.nodes[0].x = "Infinity"; expect(() => payload(invalid)).toThrow();
  });
  it("requires acknowledgement of this exact immutable v2 proposal and current context", () => {
    expect(adoptionKey(proposal)).toBe(proposal.id);
    for (const ack of ["", "other", JSON.stringify([proposal.id, proposal.graphDigest])])
      expect(() => graphActionPayload("p", "w", context, proposal, "accept", ack)).toThrow();
    expect(graphActionPayload("p", "w", context, proposal, "accept", proposal.id)).toEqual({ project: "p", workspace: "w", expectedAcceptedHead: "head", expectedGraphDigest: "digest", adoptBaseGraphDigest: null, reviewedChangesId: "proposal" });
    expect(() => graphActionPayload("p", "w", { ...context, acceptedHead: "new" }, proposal, "accept", proposal.id)).toThrow();
  });
  it("does not carry acknowledgement into a rebased immutable proposal", () => {
    expect(() => graphActionPayload("p", "w", context, { ...proposal, id: "rebased" }, "accept", proposal.id)).toThrow();
    expect(graphActionPayload("p", "w", context, proposal, "rebase", "")).not.toHaveProperty("reviewedChangesId");
  });
  it("rejects known state-only staleness but permits explicit rebase with the same graph and head", () => {
    const changed = { ...context, stateRevision: 2 };
    expect(graphProposalStale(changed, proposal)).toBe(true);
    expect(() => graphActionPayload("p", "w", changed, proposal, "accept", proposal.id)).toThrow();
    expect(graphActionPayload("p", "w", changed, proposal, "rebase", "")).toEqual({ project: "p", workspace: "w", expectedAcceptedHead: "head", expectedGraphDigest: "digest" });
  });
  it("renders all four graph states and all destructive effects as escaped text", () => {
    const hostile = '<img src=x onerror="alert(1)">';
    const html = renderToStaticMarkup(createElement(GraphChangeReview, { proposal: { ...proposal,
      stateEffects: { ...proposal.stateEffects!, effects: { removedRules: [{ id: hostile, text: "rule retained in evidence" }], unassignedTickets: [{ id: "ticket", before: "n", after: "" }] } } } }));
    for (const value of ["Accepted", "Working", "unaccepted drift", "Renamed", "rule retained in evidence", "ticket", "&lt;img"] ) expect(html).toContain(value);
    expect(html).not.toContain("<img");
  });
  it("never enables v2 acceptance without complete evidence or an explicit checkbox", () => {
    const model = { inspected: proposal, context, disabled: false, acknowledged: false, acknowledge() {}, accept() {}, rebase() {} } as unknown as GraphProposalsView;
    expect(renderToStaticMarkup(createElement(GraphProposalDetails, { model }))).toContain('disabled="">Přijmout úpravy plánu');
    const incomplete = { ...model, acknowledged: true, inspected: { ...proposal, stateEffects: undefined } };
    expect(renderToStaticMarkup(createElement(GraphProposalDetails, { model: incomplete }))).toContain('disabled="">Přijmout úpravy plánu');
  });
  it("reviews dependency boundary documents with their exact revision and all fields", () => {
    const model = { inspected: { ...proposal, architectureDocuments: [{ nodeId: "architecture", ownerWorkspace: "shared", revision: 7,
      fields: { goal: "Boundary goal", non_goals: "No shared rewrite", acceptance: "Boundary checked" } }] }, context,
      disabled: false, acknowledged: false, acknowledge() {}, accept() {}, rebase() {} } as unknown as GraphProposalsView;
    const html = renderToStaticMarkup(createElement(GraphProposalDetails, { model }));
    for (const text of ["architecture", "shared", "Revize 7", "Boundary goal", "No shared rewrite", "Boundary checked"]) expect(html).toContain(text);
  });
});
