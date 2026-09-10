import { test, expect } from "@playwright/test";

test("harness boots and renders the requested panel", async ({ page }) => {
  await page.goto("/?panel=memory&project=smoke&workspace=draft-smoke&path=");
  await expect(page.getByRole("heading", { name: "Paměť projektu" })).toBeVisible();
});
