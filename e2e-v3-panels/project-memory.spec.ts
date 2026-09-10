import { test, expect } from "@playwright/test";

function url(params: Record<string, string>) {
  const q = new URLSearchParams(params).toString();
  return `/?panel=memory&${q}`;
}

test("shows empty defaults, no demo data, for a fresh project/workspace", async ({ page }) => {
  await page.goto(url({ project: "proj-mem-empty", workspace: "draft-a", path: "src/Board.tsx" }));
  await expect(page.getByText("Zatím žádná nastavení.")).toBeVisible();
  await expect(page.getByText("Zatím žádná pravidla.")).toBeVisible();
  await expect(page.getByText("Zatím žádná rozhodnutí.")).toBeVisible();
});

test("adds a rule scoped to project, a rule scoped to path, and a pinned decision; state reloads correctly", async ({
  page,
}) => {
  const project = "proj-mem-rw";
  const workspace = "draft-b";
  await page.goto(url({ project, workspace, path: "src/Board.tsx" }));

  await page.getByLabel("Nové pravidlo").fill("NE: číst .env");
  await page.getByRole("button", { name: "Přidat pravidlo", exact: true }).click();
  await expect(page.getByText("číst .env", { exact: true })).toBeVisible();
  await expect(page.getByText("zákaz", { exact: true })).toBeVisible();

  await page.getByLabel("Rozsah pravidla").selectOption("path");
  await page.getByLabel("Nové pravidlo").fill("Dokumentovat veřejné API");
  await page.getByRole("button", { name: "Přidat pravidlo", exact: true }).click();
  await expect(page.getByText("cesta src/Board.tsx", { exact: true })).toBeVisible();

  await page.getByLabel("Nové rozhodnutí").fill("Rozhodnuto: použít digest pro ukládání.");
  await page.getByRole("button", { name: "Zapsat rozhodnutí", exact: true }).click();
  await expect(page.getByText("Rozhodnuto: použít digest pro ukládání.", { exact: true })).toBeVisible();
  await expect(page.getByText("Rozhodnutí · 1 připnuto", { exact: true })).toBeVisible();

  // Reload the whole page: persisted server state must survive, not just local React state.
  await page.reload();
  await expect(page.getByText("číst .env", { exact: true })).toBeVisible();
  await expect(page.getByText("cesta src/Board.tsx", { exact: true })).toBeVisible();
  await expect(page.getByText("Rozhodnuto: použít digest pro ukládání.", { exact: true })).toBeVisible();
  await expect(page.getByText("Rozhodnutí · 1 připnuto", { exact: true })).toBeVisible();
});

test("unpin toggles a decision without losing it", async ({ page }) => {
  const project = "proj-mem-pin";
  const workspace = "draft-c";
  await page.goto(url({ project, workspace, path: "" }));
  await page.getByLabel("Nové rozhodnutí").fill("Rozhodnuto: testovací záznam.");
  await page.getByRole("button", { name: "Zapsat rozhodnutí", exact: true }).click();
  await expect(page.getByText("Rozhodnutí · 1 připnuto", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Odepnout", exact: true }).click();
  await expect(page.getByText("Rozhodnutí · 0 připnuto", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Připnout", exact: true }).click();
  await expect(page.getByText("Rozhodnutí · 1 připnuto", { exact: true })).toBeVisible();
});

test("main workspace is read-only: mutation controls are disabled and no write is sent", async ({ page }) => {
  const project = "proj-mem-ro";
  let posted = false;
  await page.route("**/api/desktop-v3/state", async (route) => {
    if (route.request().method() === "POST") posted = true;
    await route.continue();
  });
  await page.goto(url({ project, workspace: "main", path: "" }));
  await expect(page.getByText("Main je pouze pro čtení; změny se neuloží.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Zapsat rozhodnutí", exact: true })).toBeDisabled();
  await expect(page.getByLabel("Nové rozhodnutí")).toBeDisabled();
  expect(posted).toBe(false);
});

test("scoped async does not leak across project switches (A to B to A)", async ({ page }) => {
  await page.goto(url({ project: "proj-mem-scope-a", workspace: "draft-a", path: "" }));
  await page.getByLabel("Nové rozhodnutí").fill("Rozhodnuto: patří do A.");
  await page.getByRole("button", { name: "Zapsat rozhodnutí", exact: true }).click();
  await expect(page.getByText("Rozhodnuto: patří do A.", { exact: true })).toBeVisible();

  await page.goto(url({ project: "proj-mem-scope-b", workspace: "draft-a", path: "" }));
  await expect(page.getByText("Zatím žádná rozhodnutí.")).toBeVisible();
  await expect(page.getByText("Rozhodnuto: patří do A.", { exact: true })).toHaveCount(0);

  await page.goto(url({ project: "proj-mem-scope-a", workspace: "draft-a", path: "" }));
  await expect(page.getByText("Rozhodnuto: patří do A.", { exact: true })).toBeVisible();
});

test("conflicting revision surfaces an error and reload recovers without silently overwriting", async ({ page }) => {
  const project = "proj-mem-conflict";
  const workspace = "draft-conflict";
  await page.goto(url({ project, workspace, path: "" }));
  let first = true;
  await page.route("**/api/desktop-v3/state", async (route) => {
    if (route.request().method() === "POST" && first) {
      first = false;
      await route.fulfill({ status: 409, json: { error: "Konflikt revizí; načtěte znovu." } });
      return;
    }
    await route.continue();
  });
  await page.getByLabel("Nové rozhodnutí").fill("Rozhodnuto: měl by selhat na konfliktu.");
  await page.getByRole("button", { name: "Zapsat rozhodnutí", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Konflikt revizí; načtěte znovu.");
  await expect(page.getByText("Rozhodnuto: měl by selhat na konfliktu.", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Znovu načíst", exact: true }).click();
  await page.getByLabel("Nové rozhodnutí").fill("Rozhodnuto: uspěje po znovunačtení.");
  await page.getByRole("button", { name: "Zapsat rozhodnutí", exact: true }).click();
  await expect(page.getByText("Rozhodnuto: uspěje po znovunačtení.", { exact: true })).toBeVisible();
});
