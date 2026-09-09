import { test, expect } from "@playwright/test";
test("empty Canvas is interactive, creates nested nodes and restores layer", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const start = Date.now();
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "+ Sektor", exact: true }),
  ).toBeEnabled();
  await expect(page.locator(".react-flow")).toBeVisible();
  console.log("interactive_canvas_ms", Date.now() - start);
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await page.screenshot({ path: "evidence/empty-canvas.png", fullPage: true });
  await page.getByRole("button", { name: "+ Sektor", exact: true }).click();
  await page.getByLabel("Název uzlu").fill("Testovací sektor");
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();
  await page
    .getByRole("button", { name: "Otevřít vnitřní plátno", exact: true })
    .click();
  await page.getByRole("button", { name: "+ Uzel", exact: true }).click();
  await page.getByLabel("Název uzlu").fill("Testovací uzel");
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await page.reload();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await expect(
    page.getByText("Testovací uzel", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: "evidence/nested-canvas-fixture.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "evidence/mobile-fixture.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
