import { createElement } from "react";
import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import GraphProposalDetails from "../components/GraphProposalDetails";
import type { GraphProposalsView } from "./use-graph-proposals";

it("proposal fields render as escaped text, including adoption documents and names", () => {
  const hostile = '<script>alert("x")</script>';
  const model = { inspected: { id: "id", subject: hostile, parentRevision: null, graphDigest: "digest", by: { name: hostile, kind: "agent" },
    createdAt: "2026-01-01", requiresBaseAdoption: true, accepted: false, refs: {}, inside: {},
    additions: { nodes: [{ id: "new", name: hostile, kind: "node", parentId: null, x: 1, y: 2 }], edges: [] },
    specifications: [{ nodeId: "new", fields: { goal: hostile, non_goals: "", acceptance: "" } }],
    baseGraph: { nodes: [], edges: [] }, adoptionDocuments: [{ nodeId: "old", fields: { goal: hostile, non_goals: "", acceptance: "" } }] },
    context: { acceptedHead: null, graphDigest: "digest", adoptionDocuments: [] }, disabled: false, acknowledged: false,
    acknowledge() {}, accept() {}, rebase() {} } as unknown as GraphProposalsView;
  const html = renderToStaticMarkup(createElement(GraphProposalDetails, { model }));
  expect(html).not.toContain("<script>"); expect(html).toContain("&lt;script&gt;");
  expect(html).toContain("souřadnice 1"); expect(html).toContain("old");
  expect(html).toContain('type="checkbox"');
});

it("keeps superseded proposal content readable but disables both historical mutations", () => {
  const model = { inspected: { id: "history", subject: "Historical draft", parentRevision: null,
    graphDigest: "digest", by: { name: "Heart", kind: "agent" }, createdAt: "2026-01-01",
    supersededBy: "child", latestProposalId: "latest", requiresBaseAdoption: false, accepted: false,
    refs: {}, inside: {}, additions: { nodes: [], edges: [] }, specifications: [],
    baseGraph: { nodes: [], edges: [] }, adoptionDocuments: [] },
    context: { acceptedHead: null, graphDigest: "digest", adoptionDocuments: [] }, disabled: false,
    busy: false, acknowledged: true, acknowledge() {}, accept() {}, rebase() {}, inspect() {},
  } as unknown as GraphProposalsView;
  const html = renderToStaticMarkup(createElement(GraphProposalDetails, { model }));
  expect(html).toContain("Historical draft");
  expect(html).toContain("Návrh byl nahrazen");
  expect(html).toContain('<code>latest</code>');
  expect(html).toContain('<button type="button">Otevřít aktuální návrh</button>');
  expect(html).toContain('<button type="button" disabled="">Vytvořit návrh nad aktuálním základem</button>');
  expect(html).toContain('<button type="button" disabled="">Přijmout rozšíření plánu</button>');
});
