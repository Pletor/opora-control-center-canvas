import { test, expect } from "@playwright/test";

// UI-only fixture dle skutečného adapter kontraktu, nikdy live data.
test("Live Run offers source-cited costs and memory without launching a run", async ({ page }) => {
  const writes: string[] = [];
  page.on("request", (request) => { if (request.method() !== "GET" && new URL(request.url()).pathname.startsWith("/api/")) writes.push(request.url()); });
  const run = { sourceId: "oporacc-process", runId: "wu-live-fixture", sessionId: "s-fixture", parentSessionId: null,
    stateOrigin: "OporaCC /api/process", sourceTimestamp: "2026-09-10T10:00:00Z", lastEventSeq: null,
    status: { reported: "WAITING_FOR_DECISION", liveness: "reported_by_oporacc_process" }, preview: [], cost: null,
    worktrees: ["P:/fixture/worktree"], branches: ["feat/fixture"], sourcePaths: ["src/main.py"], missing: ["runtimeMemory"],
    capabilities: { btw: { supported: false, reason: "Chybí /btw transport" }, fork: { supported: false, reason: "Chybí fork transport" } },
    telemetry: [{ runId: "bridge-fixture", available: true, source: "OporaCC GET /api/agent/bridge-fixture", sessionId: "s-fixture",
      costs: { actual_usd: 1.5, estimated_usd: 2.0, source: "Bridge GET /runs/bridge-fixture", at: "2026-09-10T10:00:00Z" },
      context: { input_tokens: 123, context_window: 200000, source: "Bridge GET /runs/bridge-fixture", at: "2026-09-10T10:00:00Z" },
      model: { name: "sonnet", provider: "anthropic" }, tools: [] }] };
  await page.route("**/api/agents/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith("/sources") ? { "oporacc-process": { available: true, status: "ok" } }
      : path.endsWith("/runs") ? { items: [run], total: 1, nextCursor: null }
      : path.endsWith("/wu-live-fixture") ? run : { items: [] };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/?screen=canvas&environment=live&mode=agents");
  const tools = page.getByRole("toolbar", { name: "Nástroje Live Run" });
  await expect(tools).toBeVisible();
  await page.locator(".agent-run-item").filter({ hasText: "wu-live-fixture" }).click();
  await expect(page.getByText("P:/fixture/worktree", { exact: true })).toBeVisible();
  await tools.getByRole("button", { name: "Náklady", exact: true }).click();
  await expect(page.getByTestId("run-actual-cost")).toHaveText("1,50 USD");
  await expect(page.getByText("Bridge GET /runs/bridge-fixture", { exact: true })).toBeVisible();
  await tools.getByRole("button", { name: "Paměť", exact: true }).click();
  await expect(page.getByText("200 000", { exact: true })).toBeVisible();
  await tools.getByRole("button", { name: "Relace", exact: true }).click();
  await expect(page.getByRole("button", { name: "/btw", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Fork", exact: true })).toBeDisabled();
  expect(writes).toEqual([]);
  await page.screenshot({ path: "evidence/desktop-v2-live-fixture.png", fullPage: true });
});
