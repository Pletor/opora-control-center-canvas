import { test, expect } from "@playwright/test";

test("root opens project setup without canvas and opens the same workspace explicitly", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Nastavení projektu", exact: true })).toBeVisible();
  await expect(page.locator(".react-flow")).toHaveCount(0);
  await expect(page.getByLabel("Typ zdroje", { exact: true })).toBeVisible();
  await page.getByLabel("Cíl projektu", { exact: true }).fill("Srozumitelný editor a podklady pro LLM");
  await page.getByRole("button", { name: "Uložit nastavení projektu", exact: true }).click();
  await expect(page.getByTestId("project-settings-status")).toContainText("Uloženo");
  await page.reload();
  await expect(page.getByLabel("Cíl projektu", { exact: true })).toHaveValue("Srozumitelný editor a podklady pro LLM");
  await page.screenshot({ path: "evidence/project-home-preview.png", fullPage: true });
  await page.getByRole("button", { name: "Otevřít Canvas", exact: true }).click();
  await expect(page.getByRole("button", { name: "Mód: Struktura", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Nastavení projektu", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Nastavení projektu", exact: true })).toBeVisible();
});
