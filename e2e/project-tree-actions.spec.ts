import { test, expect, type Page } from "@playwright/test";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Izolovaný dočasný zdroj na disku; žádná sdílená ani produkční data.
async function attach(page: Page, name: string) {
  const source = await mkdtemp(join(tmpdir(), "opora-tree-"));
  await mkdir(join(source, "src", "nested"), { recursive: true });
  await mkdir(join(source, "backend"));
  await mkdir(join(source, "tests"));
  await mkdir(join(source, "docs"));
  await writeFile(join(source, "src", "main.py"), "# real source, never rewritten by tests\n");
  await writeFile(join(source, "src", "nested", "deep.py"), "# should stay collapsed after bulk expand\n");
  await writeFile(join(source, "backend", "api.py"), "# real source\n");
  await writeFile(join(source, "tests", "test_api.py"), "# real source\n");
  await writeFile(join(source, "docs", "readme.md"), "# not part of the bulk-expand set\n");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await page.getByLabel("Cesta nebo GitHub URL", { exact: true }).fill(source);
  await page.getByLabel("Název nového projektu", { exact: true }).fill(name);
  await page.getByRole("checkbox", { name: "Potvrzuji připojení vybraného zdroje." }).check();
  await page.getByRole("button", { name: "Připojit projekt", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Pracovní prostředí" }).getByRole("button", { name: "Projekt", exact: true }))
    .toHaveAttribute("aria-pressed", "true");
  return source;
}

test("bulk expand opens only the loaded src/backend/tests directories without recursing or inventing paths", async ({ page }) => {
  const source = await attach(page, "Bulk expand tracer");
  try {
    const tree = page.getByRole("tree", { name: "Soubory pracovního prostoru" });
    await expect(tree.getByRole("button", { name: "src", exact: true })).toBeVisible();
    await expect(tree.getByRole("button", { name: "docs", exact: true })).toBeVisible();
    // Strom smí jen číst: žádný zápis ani start modelu během hromadného rozbalení.
    const writes: string[] = [];
    page.on("request", (request) => { if (request.method() !== "GET") writes.push(request.method() + " " + request.url()); });
    await page.getByRole("toolbar", { name: "Nástroje Projektu" }).getByRole("button", { name: "Rozbalit src · backend · tests", exact: true }).click();
    await expect(tree.getByRole("button", { name: "main.py", exact: true })).toBeVisible();
    await expect(tree.getByRole("button", { name: "api.py", exact: true })).toBeVisible();
    await expect(tree.getByRole("button", { name: "test_api.py", exact: true })).toBeVisible();
    // nested folder inside src is real, but bulk expand is one level only
    await expect(tree.getByRole("button", { name: "nested", exact: true })).toBeVisible();
    await expect(tree.getByRole("button", { name: "deep.py", exact: true })).toHaveCount(0);
    // docs was never named by the toolbar action, so it stays collapsed/untouched
    await expect(tree.getByRole("button", { name: "readme.md", exact: true })).toHaveCount(0);
    expect(writes).toEqual([]);
    // Lišta s novými akcemi nesmí přetéct ve standardních šířkách.
    for (const width of [1280, 1440, 1920]) {
      await page.setViewportSize({ width, height: 900 });
      const overflow = await page.getByRole("toolbar", { name: "Nástroje Projektu" }).evaluate((el) => el.scrollWidth - el.clientWidth);
      expect(overflow, `toolbar overflow at ${width}`).toBeLessThanOrEqual(1);
    }
  } finally { await rm(source, { recursive: true, force: true }); }
});

test("collapse all hides children without refetching cached pages, then search note clears search only", async ({ page }) => {
  const source = await attach(page, "Collapse cache tracer");
  try {
    const tree = page.getByRole("tree", { name: "Soubory pracovního prostoru" });
    let srcRequests = 0;
    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/api/workspace/tree**", async (route) => {
      const url = new URL(route.request().url());
      if (url.searchParams.get("path") === "src") srcRequests++;
      if (url.searchParams.get("path") === "backend") await held;
      await route.continue();
    });
    // Opožděná odpověď nesmí po Sbalit vše složku znovu rozbalit.
    await tree.getByRole("button", { name: "Rozbalit backend", exact: true }).click();
    await expect(tree.getByText("Načítám složku…")).toBeVisible();
    await page.getByRole("button", { name: "Sbalit vše", exact: true }).click();
    const backendResponse = page.waitForResponse((response) => response.url().includes("path=backend"));
    release();
    await backendResponse;
    await expect(tree.getByRole("button", { name: "Rozbalit backend", exact: true })).toBeVisible();
    await expect(tree.getByRole("button", { name: "api.py", exact: true })).toHaveCount(0);

    await tree.getByRole("button", { name: "Rozbalit src", exact: true }).click();
    await expect(tree.getByRole("button", { name: "main.py", exact: true })).toBeVisible();
    expect(srcRequests).toBe(1);
    await page.getByRole("button", { name: "Sbalit vše", exact: true }).click();
    await expect(tree.getByRole("button", { name: "main.py", exact: true })).toHaveCount(0);
    await expect(tree.getByRole("button", { name: "src", exact: true })).toBeVisible();
    // re-expanding reuses the already-loaded page; disk/state is untouched, no second fetch
    await tree.getByRole("button", { name: "Rozbalit src", exact: true }).click();
    await expect(tree.getByRole("button", { name: "main.py", exact: true })).toBeVisible();
    expect(srcRequests).toBe(1);

    await page.getByLabel("Hledat v načteném stromu", { exact: true }).fill("main.py");
    await expect(page.getByText("main.py", { exact: false }).first()).toBeVisible();
    const note = page.getByText("Hledání „main.py“", { exact: false });
    await expect(note).toBeVisible();
    await page.getByRole("complementary", { name: "Zdrojový strom" }).getByRole("button", { name: "Zrušit", exact: true }).click();
    await expect(page.getByLabel("Hledat v načteném stromu", { exact: true })).toHaveValue("");
    await expect(note).toHaveCount(0);
    // clearing the search doesn't collapse the tree that was left open
    await expect(tree.getByRole("button", { name: "main.py", exact: true })).toBeVisible();
  } finally { await rm(source, { recursive: true, force: true }); }
});

test("row keyboard controls select, expand/collapse and add a reference without hijacking editable fields", async ({ page }) => {
  const source = await attach(page, "Row keyboard tracer");
  try {
    const tree = page.getByRole("tree", { name: "Soubory pracovního prostoru" });
    const srcRow = tree.getByRole("button", { name: "src", exact: true });
    await srcRow.focus();
    await page.keyboard.press("ArrowRight");
    await expect(tree.getByRole("button", { name: "main.py", exact: true })).toBeVisible();
    await page.keyboard.press("ArrowLeft");
    await expect(tree.getByRole("button", { name: "main.py", exact: true })).toHaveCount(0);
    await page.keyboard.press("ArrowRight");
    const mainRow = tree.getByRole("button", { name: "main.py", exact: true });
    await mainRow.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "src/main.py", exact: true })).toBeVisible();
    await page.keyboard.press("Control+a");
    const environments = page.getByRole("navigation", { name: "Pracovní prostředí" });
    await environments.getByRole("button", { name: "Editor", exact: true }).click();
    const shelf = page.getByRole("complementary", { name: "Kontext Editoru" });
    await expect(shelf.getByRole("button", { name: "src/main.py", exact: true })).toHaveCount(1);
    await environments.getByRole("button", { name: "Projekt", exact: true }).click();

    // Ctrl+A must stay a native "select all" inside the search input, not a reference add.
    const search = page.getByLabel("Hledat v načteném stromu", { exact: true });
    await search.fill("backend");
    await search.focus();
    await page.keyboard.press("Control+a");
    await environments.getByRole("button", { name: "Editor", exact: true }).click();
    await expect(shelf.getByRole("button", { name: "src/main.py", exact: true })).toHaveCount(1);
    await expect(shelf.getByRole("button", { name: "backend", exact: true })).toHaveCount(0);
  } finally { await rm(source, { recursive: true, force: true }); }
});

test("per-row + Editor adds that row's path without changing the current selection, and blocks unsupported paths", async ({ page }) => {
  const source = await attach(page, "Row add tracer");
  try {
    const tree = page.getByRole("tree", { name: "Soubory pracovního prostoru" });
    await tree.getByRole("button", { name: "src", exact: true }).click();
    await expect(page.getByRole("heading", { name: "src", exact: true })).toBeVisible();
    await tree.getByRole("button", { name: "Rozbalit backend", exact: true }).click();
    const backendRow = tree.locator(".source-row", { hasText: "backend" }).first();
    // Tlačítko řádku zůstává uvnitř řádku a strom nepřetéká do inspektoru.
    const rowBox = (await backendRow.boundingBox())!;
    const addBox = (await backendRow.getByRole("button", { name: "+ Editor", exact: true }).boundingBox())!;
    expect(addBox.x + addBox.width).toBeLessThanOrEqual(rowBox.x + rowBox.width + 1);
    expect(await page.getByRole("complementary", { name: "Zdrojový strom" }).evaluate((el) => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(1);
    await backendRow.getByRole("button", { name: "+ Editor", exact: true }).click();
    await expect(page.getByRole("heading", { name: "src", exact: true })).toBeVisible();
    const environments = page.getByRole("navigation", { name: "Pracovní prostředí" });
    await environments.getByRole("button", { name: "Editor", exact: true }).click();
    const shelf = page.getByRole("complementary", { name: "Kontext Editoru" });
    await expect(shelf.getByRole("button", { name: "backend", exact: true })).toHaveCount(1);
    await environments.getByRole("button", { name: "Projekt", exact: true }).click();

    await page.getByLabel("Zobrazit i ignorované a technické soubory", { exact: true }).check();
    await mkdir(join(source, "node_modules"));
    await writeFile(join(source, "node_modules", "pkg.js"), "// not a reference target\n");
    await page.getByRole("button", { name: "Obnovit strom", exact: true }).click();
    const generatedRow = tree.locator(".source-row", { hasText: "node_modules" }).first();
    await expect(generatedRow.getByRole("button", { name: "+ Editor", exact: true })).toBeDisabled();
  } finally { await rm(source, { recursive: true, force: true }); }
});

test("'/' focuses the tree search except while typing, and stops acting once Projekt is left", async ({ page }) => {
  const source = await attach(page, "Slash focus tracer");
  try {
    const search = page.getByLabel("Hledat v načteném stromu", { exact: true });
    // Klik doprostřed body padá do editoru dokumentu; neutrální je needitovatelný nadpis stromu.
    const neutral = page.getByRole("heading", { name: "Strom projektu", exact: true });
    await neutral.click();
    await page.keyboard.press("/");
    await expect(search).toBeFocused();
    await search.fill("");
    await page.getByRole("button", { name: "src", exact: true }).click();
    await page.getByLabel("Podstata", { exact: true }).click();
    await page.keyboard.press("/");
    await expect(page.getByLabel("Podstata", { exact: true })).toHaveValue("/");
    await expect(search).not.toBeFocused();
    await page.getByLabel("Podstata", { exact: true }).fill("");

    const environments = page.getByRole("navigation", { name: "Pracovní prostředí" });
    await environments.getByRole("button", { name: "Editor", exact: true }).click();
    await page.locator("body").click();
    await page.keyboard.press("/");
    await expect(page.getByRole("toolbar", { name: "Nástroje Projektu" })).toHaveCount(0);
    // Po návratu do Projektu se posluchač znovu registruje (žádný zastaralý ref).
    await environments.getByRole("button", { name: "Projekt", exact: true }).click();
    await neutral.click();
    await page.keyboard.press("/");
    await expect(search).toBeFocused();
  } finally { await rm(source, { recursive: true, force: true }); }
});
