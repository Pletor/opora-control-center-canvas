import { test, expect } from "@playwright/test";
test("main and two real worktrees never mix their graph content", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Projekt", { exact: true }).selectOption("fixture");
  await expect(
    page.getByRole("button", { name: "+ Sektor", exact: true }),
  ).toBeDisabled();
  await page.locator(".react-flow__node").click();
  await expect(page.getByLabel("Podstata uzlu")).toHaveValue(
    "Original main purpose",
  );
  await page
    .getByRole("button", { name: "Pracovní prostor", exact: true })
    .click();
  await page
    .getByLabel("Pracovní strom")
    .selectOption({ label: "Agent A · sector1" });
  await page.locator(".react-flow__node").click();
  await page.getByLabel("Podstata uzlu").fill("Agent A isolated change");
  await page.getByLabel("Potvrzuji změnu podstaty.").check();
  await page
    .getByRole("button", { name: "Uložit podstatu", exact: true })
    .click();
  await expect(
    page.getByText("Pracovní soubory změněny", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Pracovní strom")
    .selectOption({ label: "Agent B · sector1" });
  await page.locator(".react-flow__node").click();
  await expect(page.getByLabel("Podstata uzlu")).toHaveValue(
    "Original main purpose",
  );
  await page.getByRole("button", { name: "Čistý main", exact: true }).click();
  await page.locator(".react-flow__node").click();
  await expect(page.getByLabel("Podstata uzlu")).toHaveValue(
    "Original main purpose",
  );
  await page.screenshot({ path: "evidence/main-fixture.png", fullPage: true });
});
