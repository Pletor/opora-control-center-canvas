import { test, expect } from "@playwright/test";

test("návrat A–B–A: staré potvrzení nesmaže novější draft před reloadem", async ({ page }) => {
  await page.goto("/?screen=canvas");
  for (const [name, x] of [["Návrat-A", 180], ["Návrat-B", 550]] as const) {
    await page.getByTestId("board-surface").dblclick({ position: { x, y: 110 } });
    await page.getByLabel("Jméno uzlu na plátně").fill(name);
    await page.getByLabel("Jméno uzlu na plátně").press("Enter");
  }
  const a = page.locator(".canvas-card").filter({ hasText: "Návrat-A" });
  const b = page.locator(".canvas-card").filter({ hasText: "Návrat-B" });
  const input = page.getByLabel("Text uzlu", { exact: true });
  const save = page.getByRole("button", { name: "Uložit text", exact: true });
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let started!: () => void;
  const saving = new Promise<void>(resolve => { started = resolve; });
  let held = false;
  await page.route("**/api/node-text", async route => {
    if (route.request().method() !== "POST" || held) return route.fallback();
    held = true;
    const response = await route.fetch();
    expect(response.ok()).toBeTruthy();
    started();
    await gate;
    await route.fulfill({ response });
  });
  await a.click();
  await input.fill("První verze X");
  await save.click();
  await saving;
  await b.click();
  await expect(input).toHaveValue("");
  await a.click();
  await expect(input).toHaveValue("První verze X");
  // Ruční editor nemá autosave; nový draft musí přežít i bez dalšího POST.
  await input.fill("Novější neuložený text Y");
  const oldResponse = page.waitForResponse(response =>
    new URL(response.url()).pathname === "/api/node-text" && response.request().method() === "POST");
  release();
  await (await oldResponse).finished();
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(input).toHaveValue("Novější neuložený text Y");
  await page.reload();
  await a.click();
  await expect(input).toHaveValue("Novější neuložený text Y");
  await expect(page.getByTestId("text-status")).toContainText("Neuložený text");
  await save.click();
  await expect(page.getByTestId("text-status")).toContainText("Uloženo · verze");
  await page.reload();
  await a.click();
  await expect(input).toHaveValue("Novější neuložený text Y");
});
