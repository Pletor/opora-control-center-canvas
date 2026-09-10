import { test, expect } from "@playwright/test";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("local connection opens real source tree and passes references into Editor", async ({ page }) => {
  const source = await mkdtemp(join(tmpdir(), "opora-v2-"));
  try {
    await mkdir(join(source, "src"));
    await writeFile(join(source, "src", "main.py"), "# source remains untouched\n");
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("/");
    await page.getByLabel("Cesta nebo GitHub URL", { exact: true }).fill(source);
    await page.getByLabel("Název nového projektu", { exact: true }).fill("Source tracer");
    await page.getByRole("checkbox", { name: "Potvrzuji připojení vybraného zdroje." }).check();
    await page.getByRole("button", { name: "Připojit projekt", exact: true }).click();
    const environments = page.getByRole("navigation", { name: "Pracovní prostředí" });
    await expect(environments.getByRole("button", { name: "Projekt", exact: true })).toHaveAttribute("aria-pressed", "true");
    const tree = page.getByRole("tree", { name: "Soubory pracovního prostoru" });
    await tree.getByRole("button", { name: "Rozbalit src", exact: true }).click();
    await tree.getByRole("button", { name: "main.py", exact: true }).click();
    await expect(page.getByRole("heading", { name: "src/main.py", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Přidat do kontextu", exact: true }).click();
    await page.getByRole("button", { name: "Přidat do kontextu", exact: true }).click();
    await environments.getByRole("button", { name: "Editor", exact: true }).click();
    const shelf = page.getByRole("complementary", { name: "Kontext Editoru" });
    await expect(shelf.getByRole("button", { name: "src/main.py", exact: true })).toHaveCount(1);
    await shelf.getByLabel("Poznámka ke kontextu", { exact: true }).fill("Kontext se nepřepíná s nástroji");
    await page.reload();
    await expect(shelf.getByLabel("Poznámka ke kontextu", { exact: true })).toHaveValue("Kontext se nepřepíná s nástroji");
    await shelf.getByRole("button", { name: "src/main.py", exact: true }).click();
    await expect(page.getByRole("heading", { name: "src/main.py", exact: true })).toBeVisible();
    await expect(environments.getByRole("button", { name: "Editor", exact: true })).toHaveAttribute("aria-pressed", "true");
    await page.getByLabel("Podstata", { exact: true }).fill("Dokumentace se dá používat přímo v Editoru");
    await environments.getByRole("button", { name: "Projekt", exact: true }).click();
    await expect(page.getByLabel("Podstata", { exact: true })).toHaveValue("Dokumentace se dá používat přímo v Editoru");
    await expect(tree.getByRole("button", { name: "Rozbalit src", exact: true })).toBeVisible();
    await tree.getByRole("button", { name: "Rozbalit src", exact: true }).click();
    await expect(tree.getByRole("button", { name: "main.py", exact: true })).toBeVisible();
    await page.screenshot({ path: "evidence/desktop-v2-project.png", fullPage: true });
  } finally { await rm(source, { recursive: true, force: true }); }
});

// Pouze izolovaný testovací server a fixture; žádné modely ani produkční data.
test("three environments preserve the editor while project gets its own tools", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?screen=canvas&project=draft&workspace=draft&mode=structure");
  const environments = page.getByRole("navigation", { name: "Pracovní prostředí" });
  await expect(environments.getByRole("button", { name: "Editor", exact: true })).toHaveAttribute("aria-pressed", "true");
  await environments.getByRole("button", { name: "Projekt", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Podstata a architektura", exact: true })).toBeVisible();
  await expect(page.getByRole("toolbar", { name: "Nástroje Projektu" })).toBeVisible();
  await expect(page.getByRole("button", { name: "+ Uzel", exact: true })).toHaveCount(0);
  await page.getByLabel("Podstata", { exact: true }).fill("Rozepsaná podstata bez ztráty");
  await environments.getByRole("button", { name: "Editor", exact: true }).click();
  await expect(page.locator(".react-flow").first()).toBeVisible();
  await expect(page.getByRole("toolbar", { name: "Nástroje Editoru" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mód: Text", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mód: Kreslení", exact: true })).toBeVisible();
  await environments.getByRole("button", { name: "Live Run", exact: true }).click();
  // Nový výchozí region Live workspace, starý panel Agenti je za tlačítkem Dohled běhů.
  await expect(page.getByRole("region", { name: "Live workspace", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Dohled běhů", exact: true }).click();
  await expect(page.getByRole("region", { name: "Agenti", exact: true })).toBeVisible();
  await environments.getByRole("button", { name: "Projekt", exact: true }).click();
  await expect(page.getByLabel("Podstata", { exact: true })).toHaveValue("Rozepsaná podstata bez ztráty");
  await page.getByRole("button", { name: "Uložit dokumentaci", exact: true }).click();
  await expect(page.getByTestId("document-status")).toContainText("Uloženo");
  await page.reload();
  await expect(page.getByLabel("Podstata", { exact: true })).toHaveValue("Rozepsaná podstata bez ztráty");
});
