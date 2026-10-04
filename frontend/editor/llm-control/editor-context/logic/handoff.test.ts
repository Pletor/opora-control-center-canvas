import { describe, expect, it } from "vitest";
import { parseResult, resultTemplate, verifyResult, type AcceptedResult } from "./handoff";

const scope = { project: "project", workspace: "work", nodeId: "component" };
const brief = { schema: "opora.node-brief/1", contextVersion: "original", outputContract: { request: { ...scope, expectedRevision: 4, contextVersion: "original" } } };
const draft = () => JSON.stringify({ ...JSON.parse(resultTemplate(brief)), agent: "external-agent" });

describe("Předání a návrat výsledku", () => {
  it("šablona nese původní verzi a CAS; parser je nepřepisuje ani neodvozuje ze současného UI", () => {
    expect(parseResult(draft(), scope)).toMatchObject({ ...scope, contextVersion: "original", expectedRevision: 4, output: { schema: "opora.agent-output/1" } });
    const returned = JSON.parse(draft()); returned.contextVersion = "older"; returned.expectedRevision = 1;
    expect(parseResult(JSON.stringify(returned), scope)).toMatchObject({ contextVersion: "older", expectedRevision: 1 });
  });
  it("odmítá chybějící verzi, jiný uzel, chybějícího autora a prostý výstup bez vazby", () => {
    for (const patch of [{ contextVersion: "" }, { nodeId: "other" }, { agent: "" }]) {
      expect(() => parseResult(JSON.stringify({ ...JSON.parse(draft()), ...patch }), scope)).toThrow();
    }
    expect(() => parseResult(JSON.stringify(JSON.parse(draft()).output), scope)).toThrow();
  });
  it("hlásí ověření až pro tutéž uloženou identitu, komponentu a verzi", () => {
    const accepted: AcceptedResult = { id: "result-1", nodeId: scope.nodeId, contextVersion: "original", binding: "bound", agent: "external-agent", createdAt: "2026-10-04", output: {} };
    expect(verifyResult({ items: [accepted], hasMore: false }, accepted)).toBe(accepted);
    expect(() => verifyResult({ items: [{ ...accepted, contextVersion: "other" }], hasMore: false }, accepted)).toThrow();
    expect(() => verifyResult({ items: [], hasMore: false }, accepted)).toThrow();
  });
});
