import { test, expect } from "@playwright/test";

function url(params: Record<string, string>) {
  const q = new URLSearchParams(params).toString();
  return `/?panel=live&${q}`;
}

test("a failing planning-runs source does not hide successfully loaded handoff runs", async ({ page }) => {
  const project = "proj-live-partial";
  const workspace = "draft-a";
  await page.route("**/api/llm/runs**", (route) => route.fulfill({ status: 500, json: { error: "boom" } }));
  await page.goto(url({ project, workspace, nodeId: "" }));
  await expect(page.getByText("boom")).toBeVisible();
  // Handoff section (independent source) must still resolve normally, not stay stuck/hidden.
  await expect(page.getByText("Návrhové běhy: 0 · Handoff běhy: 0")).toBeVisible();
  await expect(page.getByText("Žádná session neodpovídá filtru ani hledání.")).toBeVisible();
});

test("creates a real ticket bound to the node with explicit human authorship, persisted across reload", async ({ page }) => {
  const project = "proj-live-ticket";
  const workspace = "draft-b";
  await page.goto(url({ project, workspace, nodeId: "n1" }));
  await page.getByRole('tab', {name:'6 Tickety'}).click();
  await page.getByLabel("Název nového ticketu").fill("Ověřit kontext uzlu n1");
  await page.getByLabel("Priorita nového ticketu").selectOption("high");
  await page.getByLabel("Session ID nového ticketu").fill("run-42");
  await page.getByRole("button", { name: "Založit ticket" }).click();
  const ticketItem = page.locator(".v3-ticket", { hasText: "Ověřit kontext uzlu n1" });
  await expect(ticketItem).toBeVisible();
  await expect(ticketItem.getByText("high", { exact: true })).toBeVisible();
  await expect(ticketItem.getByText("člověk", { exact: true })).toBeVisible();
  await expect(ticketItem.getByText("run-42", { exact: true })).toBeVisible();

  await page.reload();
  await page.getByRole('tab', {name:'6 Tickety'}).click();
  await expect(page.getByText("Ověřit kontext uzlu n1")).toBeVisible();
  await expect(page.getByLabel("Stav ticketu Ověřit kontext uzlu n1")).toHaveValue("open");
  await page.getByLabel("Stav ticketu Ověřit kontext uzlu n1").selectOption("doing");
  await expect(page.getByLabel("Stav ticketu Ověřit kontext uzlu n1")).toBeEnabled();
  await page.reload();
  await page.getByRole('tab', {name:'6 Tickety'}).click();
  await expect(page.getByLabel("Stav ticketu Ověřit kontext uzlu n1")).toHaveValue("doing");
});

test("context/axis section shows real timestamped decisions and explicit 'nedostupné' for missing telemetry", async ({ page }) => {
  const project = "proj-live-context";
  const workspace = "draft-c";
  await page.goto(`/?panel=memory&project=${project}&workspace=${workspace}&path=`);
  await page.getByLabel("Nové rozhodnutí").fill("Rozhodnuto: použít live osu.");
  await page.getByRole("button", { name: "Zapsat rozhodnutí", exact: true }).click();
  await expect(page.getByText("Rozhodnuto: použít live osu.", { exact: true })).toBeVisible();

  await page.goto(url({ project, workspace, nodeId: "" }));
  await page.getByRole('tab', {name:'7 Kontext a osa'}).click();
  await expect(page.getByRole("heading", { name: "Kontext a osa" })).toBeVisible();
  await expect(page.getByText("Rozhodnutí: Rozhodnuto: použít live osu.")).toBeVisible();
  await expect(page.getByText(/Kontextové okno: nedostupné/)).toBeVisible();
  await expect(page.getByText(/Průběh kompaktace: nedostupné/)).toBeVisible();
});
