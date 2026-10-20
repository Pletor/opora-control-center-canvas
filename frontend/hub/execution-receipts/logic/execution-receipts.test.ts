import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import ExecutionReceipts from "../components/ExecutionReceipts";
import type { ExecutionReceiptsView } from "./use-execution-receipts";
import { ReceiptRequests, executionLabel, executionQuery, readExecutionHistory, readExecutionReceipts, receiptDetails, unixTime, type ExecutionSummary, type ExecutionReceipt, type ReadApi } from "./execution-receipts";

const run: ExecutionSummary = { executionId: "exec1", project: "project", workspace: "workspace", nodeId: "node",
  epoch: 1, acceptedRevision: "accepted", assignmentDigest: "digest", expiresAt: 200, serverNow: 100, state: "running" };
const receipt: ExecutionReceipt = { receiptId: "receipt1", executionId: "exec1", requestId: "request1", result: {
  summary: '<script>alert("injected")</script>', evidence: { url: "javascript:alert(1)", command: "delete everything" } },
  state: "reported", acceptedRevision: "accepted", assignmentDigest: "digest", verification: "agent-reported; not independently verified", createdAt: "2026-10-20T12:00:00Z" };

describe("execution receipt reads", () => {
  it("establishes human UI session before identified history and context GETs", async () => {
    const urls: string[] = [];
    const read = (async (url: string) => { urls.push(url); return url.includes("/context?")
      ? { available: true, acceptedHead: "accepted" } : { executions: [run] }; }) as ReadApi;
    const result = await readExecutionHistory(read, "project", "workspace", "node");
    expect(urls[0]).toBe("/api/access/ui-session");
    expect(urls.slice(1)).toEqual(["/api/oporahub/executions/context?project=project&workspace=workspace&nodeId=node",
      "/api/oporahub/executions?project=project&workspace=workspace&nodeId=node"]);
    expect(result.executions).toEqual([run]);
  });
  it("reads only scoped receipts, never assignment or execution token", async () => {
    const urls: string[] = [];
    const read = (async (url: string) => { urls.push(url); return { results: [receipt] }; }) as ReadApi;
    await readExecutionReceipts(read, "p&other=1", "w", "id/with?query");
    expect(urls).toEqual(["/api/access/ui-session", "/api/oporahub/executions/id%2Fwith%3Fquery/results?project=p%26other%3D1&workspace=w"]);
    expect(executionQuery("p", "w", "n&x=y")).toBe("project=p&workspace=w&nodeId=n%26x%3Dy");
  });
  it("does not proceed when session establishment fails", async () => {
    const urls: string[] = [];
    const read = (async (url: string) => { urls.push(url); throw new Error("Session unavailable"); }) as ReadApi;
    await expect(readExecutionHistory(read, "p", "w", "n")).rejects.toThrow("Session unavailable");
    expect(urls).toEqual(["/api/access/ui-session"]);
  });
  it("ignores late old scope/selection responses and invalidates refresh or unmount", async () => {
    const requests = new ReceiptRequests();
    const first = requests.next();
    let release!: () => void;
    const delayed = new Promise<void>(resolve => { release = resolve; });
    const painted: string[] = [];
    const previous = delayed.then(() => { if (first()) painted.push("old project/selection"); });
    requests.invalidate();
    const second = requests.next();
    if (second()) painted.push("new selection");
    release(); await previous;
    expect(painted).toEqual(["new selection"]);
    requests.invalidate(); expect(second()).toBe(false);
  });
});

it("uses numeric server seconds and never presents reported or expired as verified", () => {
  expect(executionLabel(run)).toBe("Aktivní při načtení");
  expect(executionLabel({ ...run, serverNow: 200 })).toBe("Oprávnění vypršelo");
  expect(executionLabel({ ...run, expiresAt: NaN })).toBe("Autorita nedoložena");
  expect(executionLabel({ ...run, state: "reported" })).toBe("Výsledek nahlášen");
  expect(executionLabel({ ...run, state: "revoked" })).toBe("Oprávnění již neplatí");
  expect(unixTime(Infinity)).toBe("Čas není dostupný");
});

it("renders untrusted results as escaped text without links, scripts or executable commands", () => {
  const model = { choices: [], nodeId: "node", project: "project", workspace: "workspace", selected: { ...run, state: "reported" },
    receipts: [receipt], executions: [], context: { acceptedHead: "newer" }, busy: false,
    detailBusy: false, detailError: "", error: "", refresh() {}, selectCard() {}, selectExecution() {},
  } as unknown as ExecutionReceiptsView;
  const html = renderToStaticMarkup(createElement(ExecutionReceipts, { model }));
  expect(html).not.toContain("<script>");
  expect(html).not.toContain('href="javascript:');
  expect(html).toContain("&lt;script&gt;");
  expect(html).toContain("starší přijaté revizi");
  expect(html).toContain("Nahlášený výsledek není nezávislé ověření");
  expect(receiptDetails(receipt)).toContain("javascript:alert(1)");
  expect(receiptDetails(receipt)).not.toContain("summary");
});
