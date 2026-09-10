import { test, expect } from "@playwright/test";

function url(params: Record<string, string>) {
  const q = new URLSearchParams(params).toString();
  return `/?panel=workflow&${q}`;
}

test("defaults to discover phase with empty criteria and steps", async ({ page }) => {
  await page.goto(url({ project: "proj-wf-empty", workspace: "draft-a", nodeId: "n1" }));
  await expect(page.getByRole("tab", { name: "Objev" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Zatím žádná kritéria.")).toBeVisible();
  await expect(page.getByText("Zatím žádné kroky.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Postoupit/ })).toBeDisabled();
});

test("advance is blocked until all criteria are checked, then advances and persists", async ({ page }) => {
  const project = "proj-wf-advance";
  const workspace = "draft-b";
  await page.goto(url({ project, workspace, nodeId: "n1" }));

  await page.getByLabel("Nové kritérium").fill("Cíl je popsán");
  await page.getByRole("button", { name: "Přidat kritérium", exact: true }).click();
  await page.getByLabel("Nové kritérium").fill("Cesty jsou v kontextu");
  await page.getByRole("button", { name: "Přidat kritérium", exact: true }).click();
  await expect(page.getByRole("button", { name: /Postoupit/ })).toBeDisabled();

  await page.getByRole("checkbox").nth(0).check();
  await expect(page.getByRole("button", { name: /Postoupit/ })).toBeDisabled();
  await page.getByRole("checkbox").nth(1).check();
  await expect(page.getByRole("button", { name: /Postoupit → Definice/ })).toBeEnabled();

  await page.getByRole("button", { name: /Postoupit → Definice/ }).click();
  await expect(page.getByRole("tab", { name: "Definice" })).toHaveAttribute("aria-selected", "true");

  await page.reload();
  await expect(page.getByRole("tab", { name: "Definice" })).toHaveAttribute("aria-selected", "true");
});

test("can move back to an earlier phase without criteria, but not forward without checking off a later phase button", async ({
  page,
}) => {
  const project = "proj-wf-back";
  const workspace = "draft-c";
  await page.goto(url({ project, workspace, nodeId: "n1" }));
  await page.getByLabel("Nové kritérium").fill("jedno kritérium");
  await page.getByRole("button", { name: "Přidat kritérium", exact: true }).click();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /Postoupit → Definice/ }).click();
  await expect(page.getByRole("tab", { name: "Definice" })).toHaveAttribute("aria-selected", "true");

  await page.getByRole("tab", { name: "Objev" }).click();
  await expect(page.getByRole("tab", { name: "Objev" })).toHaveAttribute("aria-selected", "true");
  // Forward jump buttons for phases beyond current are disabled (must use Advance).
  await expect(page.getByRole("tab", { name: "Build" })).toBeDisabled();
});

test("steps can be added, marked done, and removed; done count updates", async ({ page }) => {
  const project = "proj-wf-steps";
  const workspace = "draft-d";
  await page.goto(url({ project, workspace, nodeId: "n1" }));
  await page.getByLabel("Nový krok").fill("Napsat testy");
  await page.getByLabel("Přiřazení kroku").fill("builder");
  await page.getByRole("button", { name: "Přidat krok", exact: true }).click();
  await expect(page.getByText("Napsat testy")).toBeVisible();
  await expect(page.getByText("0 / 1 hotovo")).toBeVisible();

  await page.getByRole("checkbox", { name: "Krok 1 hotovo" }).check();
  await expect(page.getByText("1 / 1 hotovo")).toBeVisible();

  await page.getByRole("button", { name: "Odebrat", exact: true }).click();
  await expect(page.getByText("Zatím žádné kroky.")).toBeVisible();
});

test("toggling a criterion checkbox does not change run status text elsewhere on the page", async ({ page }) => {
  const project = "proj-wf-run-status";
  const workspace = "draft-e";
  await page.goto(url({ project, workspace, nodeId: "n1" }));
  await page.getByLabel("Nové kritérium").fill("kontrolní bod");
  await page.getByRole("button", { name: "Přidat kritérium", exact: true }).click();
  const before = await page.content();
  await page.getByRole("checkbox").check();
  const after = await page.content();
  // Only the checkbox state and Advance-button enablement should change; assert no unrelated
  // "run"/status wording appears anywhere as a side effect of a plain checklist toggle.
  expect(after).not.toContain("run status");
  expect(before).not.toContain("run status");
});

test("independent node ids keep separate workflow state", async ({ page }) => {
  const project = "proj-wf-multi";
  const workspace = "draft-f";
  await page.goto(url({ project, workspace, nodeId: "n1" }));
  await page.getByLabel("Nový krok").fill("Krok pro n1");
  await page.getByRole("button", { name: "Přidat krok", exact: true }).click();
  await expect(page.getByText("Krok pro n1")).toBeVisible();

  await page.goto(url({ project, workspace, nodeId: "n2" }));
  await expect(page.getByText("Zatím žádné kroky.")).toBeVisible();
  await expect(page.getByText("Krok pro n1")).toHaveCount(0);

  await page.goto(url({ project, workspace, nodeId: "n1" }));
  await expect(page.getByText("Krok pro n1")).toBeVisible();
});
