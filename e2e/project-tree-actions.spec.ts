import { test, expect, type Page } from "@playwright/test";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Skutečná dočasná zdrojová složka připojená přes UI; frontend nedostává žádná vymyšlená data.
async function connect(page: Page, source: string, name: string) {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await page.getByLabel("Cesta nebo GitHub URL", { exact: true }).fill(source);
  await page.getByLabel("Název nového projektu", { exact: true }).fill(name);
  await page.getByRole("checkbox", { name: "Potvrzuji připojení vybraného zdroje." }).check();
  await page.getByRole("button", { name: "Připojit projekt", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Pracovní prostředí" }).getByRole("button", { name: "Projekt", exact: true })).toHaveAttribute("aria-pressed", "true");
  return page.getByRole("tree", { name: "Soubory pracovního prostoru" });
}

test("toolbar expands only loaded src/backend/tests folders with GET-only tree loads", async ({ page }) => {
  const source = await mkdtemp(join(tmpdir(), "opora-tree-"));
  try {
    for (const dir of ["src", "backend", "tests", "docs"]) { await mkdir(join(source, dir)); await writeFile(join(source, dir, dir + "-file.txt"), "x\n"); }
    const tree = await connect(page, source, "Tree expand tracer");
    await expect(tree.getByRole("button", { name: "Rozbalit docs", exact: true })).toBeVisible();
    const requests: string[] = [];
    page.on("request", (request) => requests.push(request.method() + " " + new URL(request.url()).pathname));
    await page.getByRole("toolbar", { name: "Nástroje Projektu" }).getByRole("button", { name: "Rozbalit src, backend, tests", exact: true }).click();
    for (const dir of ["src", "backend", "tests"]) {
      await expect(tree.getByRole("button", { name: "Sbalit " + dir, exact: true })).toBeVisible();
      await expect(tree.getByRole("button", { name: dir + "-file.txt", exact: true })).toBeVisible();
    }
    await expect(tree.getByRole("button", { name: "Rozbalit docs", exact: true })).toBeVisible();
    await expect(tree.getByRole("button", { name: "docs-file.txt", exact: true })).toHaveCount(0);
    expect(requests.filter((line) => !line.startsWith("GET "))).toEqual([]);
    expect(requests.filter((line) => line.startsWith("GET /api/workspace/tree")).length).toBe(3);
  } finally { await rm(source, { recursive: true, force: true }); }
});

test("collapse all keeps folders collapsed while a child fetch finishes later and keeps loaded pages", async ({ page }) => {
  const source = await mkdtemp(join(tmpdir(), "opora-tree-"));
  try {
    for (const dir of ["src", "backend"]) { await mkdir(join(source, dir)); await writeFile(join(source, dir, dir + "-file.txt"), "x\n"); }
    const tree = await connect(page, source, "Tree collapse tracer");
    const toolbar = page.getByRole("toolbar", { name: "Nástroje Projektu" });
    // Skutečná odpověď serveru jen pozdržená, aby dorazila až po sbalení.
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    await page.route((url) => url.pathname === "/api/workspace/tree" && url.searchParams.get("path") === "src", async (route) => { await gate; await route.continue(); });
    const requests: string[] = [];
    page.on("request", (request) => requests.push(request.method() + " " + new URL(request.url()).pathname + " " + new URL(request.url()).searchParams.get("path")));
    await toolbar.getByRole("button", { name: "Rozbalit src, backend, tests", exact: true }).click();
    await expect(tree.getByRole("button", { name: "backend-file.txt", exact: true })).toBeVisible();
    await expect(tree.getByRole("status")).toHaveText("Načítám složku…");
    await toolbar.getByRole("button", { name: "Sbalit vše", exact: true }).click();
    await expect(tree.getByRole("button", { name: "Rozbalit src", exact: true })).toBeVisible();
    await expect(tree.getByRole("button", { name: "Rozbalit backend", exact: true })).toBeVisible();
    const late = page.waitForResponse((response) => new URL(response.url()).searchParams.get("path") === "src");
    release();
    await late;
    await expect(tree.getByRole("button", { name: "Rozbalit src", exact: true })).toBeVisible();
    await expect(tree.getByRole("button", { name: "src-file.txt", exact: true })).toHaveCount(0);
    await tree.getByRole("button", { name: "Rozbalit backend", exact: true }).click();
    await expect(tree.getByRole("button", { name: "backend-file.txt", exact: true })).toBeVisible();
    await tree.getByRole("button", { name: "Rozbalit src", exact: true }).click();
    await expect(tree.getByRole("button", { name: "src-file.txt", exact: true })).toBeVisible();
    expect(requests.filter((line) => !line.startsWith("GET "))).toEqual([]);
    expect(requests.filter((line) => line === "GET /api/workspace/tree backend").length).toBe(1);
    expect(requests.filter((line) => line === "GET /api/workspace/tree src").length).toBe(1);
  } finally { await rm(source, { recursive: true, force: true }); }
});
