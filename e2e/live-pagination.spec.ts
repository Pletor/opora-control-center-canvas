import { test, expect } from "@playwright/test";

test("Live Run exposes later pages instead of hiding runs after the first thirty", async ({ page }) => {
  await page.route("**/api/agents/**", (route) => {
    const url = new URL(route.request().url());
    const cursor = Number(url.searchParams.get("cursor") ?? 0);
    const row = (id: string) => ({ sourceId: "fixture", runId: id, sessionId: null, stateOrigin: "fixture", sourceTimestamp: null,
      lastEventSeq: null, status: { reported: "stopped", liveness: "reported_stopped" }, preview: [], cost: null, missing: [] });
    const body = url.pathname.endsWith("/sources") ? { fixture: { available: true } }
      : url.pathname.endsWith("/runs") ? { items: Array.from({ length: cursor === 0 ? 30 : 1 }, (_, i) => row(`fixture-${cursor + i}`)), total: 31, nextCursor: cursor === 0 ? 30 : null }
      : { items: [] };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/?screen=canvas&mode=agents");
  await expect(page.locator(".agent-run-item")).toHaveCount(30);
  await page.getByRole("button", { name: "Další relace", exact: true }).click();
  await expect(page.locator(".agent-run-item")).toHaveCount(1);
  await expect(page.locator(".agent-run-item").first()).toContainText("fixture-30");
  await page.getByRole("button", { name: "Předchozí relace", exact: true }).click();
  await expect(page.locator(".agent-run-item")).toHaveCount(30);
});
