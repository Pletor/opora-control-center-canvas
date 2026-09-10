import { test, expect } from "@playwright/test";

test("pozdní odpověď deníku A nesmí uložit text dne B do A", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await page.getByTestId("board-surface").dblclick({ position: { x: 200, y: 120 } });
  await page.getByLabel("Jméno uzlu na plátně").fill("Dny");
  await page.getByLabel("Jméno uzlu na plátně").press("Enter");
  await page.locator(".canvas-card").filter({ hasText: "Dny" }).click();
  await page.getByRole("button", { name: "Otevřít vnitřní plátno", exact: true }).click();
  await page.getByRole("button", { name: "Mód: Text", exact: true }).click();
  await page.getByRole("tab", { name: "Deník", exact: true }).click();
  const date = page.getByLabel("Den zápisu");
  const entry = page.getByTestId("journal-blocks").getByLabel("Zápis dne · blok 1");
  const dayA = "2026-01-10", dayB = "2026-01-11";
  await date.fill(dayA);
  await expect(entry).toHaveValue("");
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let started!: () => void;
  const saving = new Promise<void>(resolve => { started = resolve; });
  let scope: Record<string, string> = {};
  let held = false;
  await page.route("**/api/node-journal", async route => {
    if (route.request().method() !== "POST") return route.fallback();
    const payload = route.request().postDataJSON();
    if (payload.day !== dayA || held) return route.fallback();
    held = true;
    scope = { project: payload.project, workspace: payload.workspace, node: payload.node };
    const response = await route.fetch();
    started();
    await gate;
    await route.fulfill({ response });
  });
  await entry.fill("Pouze den A");
  await saving;
  await date.fill(dayB);
  await expect(entry).toHaveValue("");
  await entry.fill("Pouze den B");
  release();
  await expect(page.getByTestId("journal-status")).toContainText("Uloženo · verze", { timeout: 10000 });
  const read = async (day: string) => {
    const response = await page.request.get("/api/node-journal?" + new URLSearchParams({ ...scope, day }));
    expect(response.ok()).toBeTruthy();
    return response.json();
  };
  // Server uchovává markdownový blok, nikoli jen text vstupního pole.
  await expect.poll(async () => (await read(dayB)).text).toBe("- Pouze den B");
  expect((await read(dayA)).text).toBe("- Pouze den A");
  await page.reload();
  await page.getByRole("tab", { name: "Deník", exact: true }).click();
  await page.getByLabel("Den zápisu").fill(dayB);
  await expect(entry).toHaveValue("Pouze den B");
});
