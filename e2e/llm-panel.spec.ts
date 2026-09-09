import { test, expect } from "@playwright/test";

test("saved planning preview is connected to project home without automatic paid start", async ({ page }) => {
  let starts = 0; page.on("request", r => { if (r.url().endsWith("/api/llm/start")) starts++; });
  await page.goto("/");
  await page.getByRole("button", { name: "Náhled kontextu návrhu", exact: true }).click();
  await expect(page.getByTestId("llm-preview")).toContainText("proposal_only");
  await expect(page.getByTestId("llm-preview")).toContainText("wireframe");
  await page.getByLabel("Cíl projektu", { exact: true }).fill("Neuložená změna");
  await expect(page.getByRole("button", { name: "Potvrdit a spustit návrh", exact: true })).toBeDisabled();
  expect(starts).toBe(0);
});
