import { test, expect } from "@playwright/test";

test("panel Agenti je dostupný z plátna a jeho otevření nic nespouští", async ({ page }) => {
  const writes: string[] = [];
  const reads: string[] = [];
  page.on("request", request => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/agents/")) reads.push(path);
    if (request.method() === "POST" && /^\/api\/(agents|coding|llm)\//.test(path)) writes.push(path);
  });
  // UI fixture nečte osobní logy ani živý Bridge. Skutečný router kryje backendový integrační test.
  await page.route("**/api/agents/**", route => {
    const path = new URL(route.request().url()).pathname;
    const data = path.endsWith("/sources")
      ? { "hermes-orchestrator": { available: false, error: "fixture_missing_source" } }
      : path.endsWith("/runs") ? { items: [], total: 0, nextCursor: null }
      : { items: [] };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
  });
  await page.goto("/?screen=canvas");
  await page.getByRole("button", { name: "Live Run", exact: true }).click();
  await expect(page.getByRole("region", { name: "Agenti", exact: true })).toBeVisible();
  await expect(page.getByText("hermes-orchestrator: fixture_missing_source", { exact: true })).toBeVisible();
  await expect(page.getByText("Žádné běhy z nakonfigurovaných zdrojů.", { exact: true })).toBeVisible();
  expect(reads).toContain("/api/agents/sources");
  expect(reads).toContain("/api/agents/runs");
  expect(writes).toEqual([]);
  await page.getByRole("button", { name: "Editor", exact: true }).click();
  await page.getByRole("button", { name: "Mód: Struktura", exact: true }).click();
  await expect(page.getByTestId("board-surface")).toBeVisible();
  await expect(page.getByRole("region", { name: "Agenti", exact: true })).toHaveCount(0);
  expect(writes).toEqual([]);
});
