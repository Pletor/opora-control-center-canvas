import { test, expect } from "@playwright/test";

for (const mode of ["detail", "text"] as const) {
  test(`souvislosti se obnoví po uložení bez reloadu: ${mode}`, async ({ page }) => {
    await page.goto("/?screen=canvas");
    const source = `Zdroj-${mode}`, target = `Cíl-${mode}`;
    for (const [name, x] of [[source, 180], [target, 550]] as const) {
      await page.getByTestId("board-surface").dblclick({ position: { x, y: 110 } });
      await page.getByLabel("Jméno uzlu na plátně").fill(name);
      await page.getByLabel("Jméno uzlu na plátně").press("Enter");
    }
    await page.locator(".canvas-card").filter({ hasText: source }).click();
    if (mode === "text") {
      await page.getByRole("button", { name: "Otevřít vnitřní plátno", exact: true }).click();
      await page.getByRole("button", { name: "Mód: Text", exact: true }).click();
    }
    const count = page.getByTestId("link-out-count");
    const editor = page.getByTestId("node-blocks").getByLabel("Bloky uzlu · blok 1");
    await expect(count).toHaveText("0");
    await editor.fill(`[[${target}]]`);
    await expect(page.getByTestId("text-status")).toContainText("Uloženo · verze");
    await expect(count).toHaveText("1");
    await expect(page.getByTestId("link-out")).toContainText(target);
    await editor.fill("Bez odkazu");
    await expect(count).toHaveText("0");
  });
}
