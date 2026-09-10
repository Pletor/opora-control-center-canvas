import { test, expect } from "@playwright/test";

test("karty inspektoru mají šipky, Home/End a jeden tabulační vstup", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await page.getByTestId("board-surface").dblclick({ position: { x: 200, y: 120 } });
  await page.getByLabel("Jméno uzlu na plátně").fill("Klávesnice karet");
  await page.getByLabel("Jméno uzlu na plátně").press("Enter");
  // Počkáme na uložené přejmenování: změna graph digestu znovu připojuje inspektor.
  await expect(page.getByRole("complementary", { name: "Inspektor" }).getByRole("heading", { name: "Klávesnice karet", exact: true })).toBeVisible();
  const list = page.getByRole("tablist", { name: "Části uzlu" });
  const content = list.getByRole("tab", { name: "Obsah", exact: true });
  const spec = list.getByRole("tab", { name: "Zadání", exact: true });
  const work = list.getByRole("tab", { name: "Práce", exact: true });
  await content.focus();
  await content.press("ArrowRight");
  await expect(spec).toBeFocused();
  await expect(spec).toHaveAttribute("aria-selected", "true");
  await expect(page.getByLabel("Cíl práce")).toBeVisible();
  await page.getByLabel("Podstata uzlu").fill("Nesmí se ztratit přepínáním");
  await spec.focus();
  await spec.press("End");
  await expect(work).toBeFocused();
  await expect(work).toHaveAttribute("aria-selected", "true");
  await work.press("ArrowRight");
  await expect(content).toBeFocused();
  await expect(content).toHaveAttribute("aria-selected", "true");
  await content.press("ArrowLeft");
  await expect(work).toBeFocused();
  await work.press("Home");
  await expect(content).toBeFocused();
  await content.press("ArrowRight");
  await expect(spec).toBeFocused();
  await expect(page.getByLabel("Podstata uzlu")).toHaveValue("Nesmí se ztratit přepínáním");
  await expect(spec).toHaveAttribute("tabindex", "0");
  await expect(content).toHaveAttribute("tabindex", "-1");
  await expect(work).toHaveAttribute("tabindex", "-1");
  await spec.press("Tab");
  await expect(page.getByLabel("Cíl práce")).toBeFocused();
});
