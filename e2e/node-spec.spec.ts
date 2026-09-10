import { test, expect } from "@playwright/test";

/** Zadání uzlu je v inspektoru na kartě Zadání (WU-CLEAN-DESIGN). */
async function openSpec(page: import("@playwright/test").Page) {
  await page.getByRole("tab", { name: "Zadání", exact: true }).click();
}

test("node assignment saves and survives reload", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await expect(page.locator(".local-status")).toHaveText("LOKÁLNĚ · " + new URL(page.url()).port);
  await page.getByRole("button", { name: "+ Uzel", exact: true }).click();
  await page.getByLabel("Název uzlu").fill("Zadání R01");
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();
  await openSpec(page);
  await page.getByLabel("Cíl práce").fill("Přesné zadání z editoru");
  await page.getByLabel("Co není součástí").fill("Žádné spouštění agenta");
  await page.getByLabel("Podmínky dokončení").fill("Text přežije reload");
  await page.getByRole("button", { name: "Uložit zadání", exact: true }).click();
  await expect(page.getByTestId("spec-status")).toContainText("Uloženo · verze 1");
  await page.reload();
  await page.locator(".react-flow__node").filter({ hasText: "Zadání R01" }).click();
  await openSpec(page);
  await expect(page.getByLabel("Cíl práce")).toHaveValue("Přesné zadání z editoru");
  await expect(page.getByLabel("Co není součástí")).toHaveValue("Žádné spouštění agenta");
  await expect(page.getByLabel("Podmínky dokončení")).toHaveValue("Text přežije reload");
  await page.screenshot({ path: "evidence/r01-editor.png", fullPage: true });
});

async function newNode(page: import("@playwright/test").Page, name: string) {
  await page.getByRole("button", { name: "+ Uzel", exact: true }).click();
  await page.getByLabel("Název uzlu").fill(name);
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();
  await openSpec(page);
  await expect(page.getByLabel("Cíl práce")).toBeEnabled();
}

test("unsaved assignment survives switching nodes", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await newNode(page, "Rozepsané A");
  await page.getByLabel("Cíl práce").fill("Neztratit při přepnutí");
  await newNode(page, "Rozepsané B");
  await page.locator(".react-flow__node").filter({ hasText: "Rozepsané A" }).click();
  await expect(page.getByLabel("Cíl práce")).toHaveValue("Neztratit při přepnutí");
  await page.getByRole("button", { name: "Uložit zadání", exact: true }).click();
  await expect(page.getByTestId("spec-status")).toContainText("Uloženo · verze 1");
});

test("two editor windows show conflict without losing local text", async ({ page, context }) => {
  await page.goto("/?screen=canvas");
  await newNode(page, "Souběh R01");
  const second = await context.newPage();
  await second.goto("/?screen=canvas");
  await second.locator(".react-flow__node").filter({ hasText: "Souběh R01" }).click();
  await openSpec(second);
  await second.getByLabel("Cíl práce").fill("Text druhého okna");
  await page.getByLabel("Cíl práce").fill("První schválený text");
  await page.getByRole("button", { name: "Uložit zadání", exact: true }).click();
  await expect(page.getByTestId("spec-status")).toContainText("Uloženo · verze 1");
  await second.getByRole("button", { name: "Uložit zadání", exact: true }).click();
  await expect(second.getByRole("alert")).toContainText("Konflikt");
  await expect(second.getByLabel("Cíl práce")).toHaveValue("Text druhého okna");
  await second.close();
});

test("main assignment is visibly read-only and unavailable", async ({ page }) => {
  await page.goto("/?project=fixture&workspace=main");
  await page.locator(".react-flow__node").first().click();
  await openSpec(page);
  await expect(page.getByText("Import zadání z Git mainu zatím není podporovaný.")).toBeVisible();
  await expect(page.getByLabel("Cíl práce")).not.toBeEditable();
  await expect(page.getByRole("button", { name: "Uložit zadání", exact: true })).toHaveCount(0);
});

test("failed save preserves text and retry succeeds", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await newNode(page, "Chyba uložení R01");
  await page.getByLabel("Cíl práce").fill("Tento text nesmí zmizet");
  await page.route("**/api/node-spec", (route) => route.fulfill({ status: 503, json: { error: "Úložiště dočasně nedostupné" } }));
  await page.getByRole("button", { name: "Uložit zadání", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("nedostupné");
  await expect(page.getByLabel("Cíl práce")).toHaveValue("Tento text nesmí zmizet");
  await page.unroute("**/api/node-spec");
  await page.getByRole("button", { name: "Uložit zadání", exact: true }).click();
  await expect(page.getByTestId("spec-status")).toContainText("Uloženo · verze 1");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByLabel("Cíl práce").scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "evidence/r01-mobile.png", fullPage: true });
});

test("late response cannot overwrite another selected node", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await newNode(page, "Pozdní A");
  const a = await page.locator(".react-flow__node").filter({ hasText: "Pozdní A" }).getAttribute("data-id");
  await newNode(page, "Pozdní B");
  await page.getByLabel("Cíl práce").fill("Aktivní zadání B");
  let release!: () => void;
  let arrived!: () => void;
  const hold = new Promise<void>((resolve) => { release = resolve; });
  const started = new Promise<void>((resolve) => { arrived = resolve; });
  await page.route("**/api/node-spec?*", async (route) => {
    if (new URL(route.request().url()).searchParams.get("node") !== a) return route.continue();
    const response = await route.fetch();
    arrived();
    await hold;
    await route.fulfill({ response });
  });
  await page.locator(".react-flow__node").filter({ hasText: "Pozdní A" }).click();
  await started;
  await page.locator(".react-flow__node").filter({ hasText: "Pozdní B" }).click();
  await expect(page.getByLabel("Cíl práce")).toHaveValue("Aktivní zadání B");
  const response = page.waitForResponse((r) => new URL(r.url()).searchParams.get("node") === a);
  release();
  await response;
  await expect(page.getByLabel("Cíl práce")).toHaveValue("Aktivní zadání B");
});
