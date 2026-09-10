import { test, expect, type Page, type Route } from "@playwright/test";

/** Nový uzel vzniká dvojklikem na prázdné plátno a hned se pojmenuje na místě. */
async function createOnCanvas(page: Page, name: string, position: { x: number; y: number }) {
  await page.getByTestId("board-surface").dblclick({ position });
  const rename = page.getByLabel("Jméno uzlu na plátně");
  await expect(rename).toBeFocused();
  await rename.fill(name);
  await rename.press("Enter");
  await expect(page.locator(".canvas-card").filter({ hasText: name })).toBeVisible();
}

/**
 * Řízeně zpožděné a odmítnuté uložení: pouze zápis, čtení jde dál na server.
 * Vrácená funkce odmítání vypne, aby šlo ověřit, že tentýž text nakonec projde.
 */
async function rejectSaves(page: Page, path: string) {
  let rejecting = true;
  await page.route(
    (url) => url.pathname === path,
    async (route: Route) => {
      if (!rejecting || route.request().method() !== "POST") return route.fallback();
      await new Promise((resolve) => setTimeout(resolve, 400));
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "Uložení dočasně selhalo." }),
      });
    },
  );
  return () => {
    rejecting = false;
  };
}

test("rozepsaný blok uzlu přežije odmítnuté uložení, přepnutí uzlu i reload", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await expect(page.getByTestId("board-hint")).toBeVisible();
  await createOnCanvas(page, "Bezpečný draft A", { x: 180, y: 110 });
  await createOnCanvas(page, "Bezpečný draft B", { x: 560, y: 110 });
  const acceptSaves = await rejectSaves(page, "/api/node-text");

  const alfa = page.locator(".canvas-card").filter({ hasText: "Bezpečný draft A" });
  const beta = page.locator(".canvas-card").filter({ hasText: "Bezpečný draft B" });
  const block = page.getByTestId("node-blocks").getByLabel("Bloky uzlu · blok 1");
  const status = page.getByTestId("text-status");

  await alfa.click();
  await block.fill("Rozepsaná myšlenka");
  await expect(status).toContainText("Neuložený text");

  // Přepnutí uzlu dřív, než uložení doběhne, nesmí text zahodit.
  await beta.click();
  await expect(block).toHaveValue("");
  await alfa.click();
  await expect(block).toHaveValue("Rozepsaná myšlenka");
  await expect(status).toContainText("Neulož");

  // Reload během neúspěšného ukládání: text zůstává uživateli, ne jen v odeslaném požadavku.
  await page.reload();
  await page.locator(".canvas-card").filter({ hasText: "Bezpečný draft A" }).click();
  await expect(block).toHaveValue("Rozepsaná myšlenka");
  await expect(status).toContainText("Neulož");

  // Jakmile server přijímá, tentýž text se uloží a přežije další reload.
  acceptSaves();
  await page.getByRole("button", { name: "Uložit text", exact: true }).click();
  await expect(status).toContainText("Uloženo · verze", { timeout: 8000 });
  await page.reload();
  await page.locator(".canvas-card").filter({ hasText: "Bezpečný draft A" }).click();
  await expect(block).toHaveValue("Rozepsaná myšlenka");
  await expect(status).toContainText("Uloženo · verze");
});

test("rozepsaný deník přežije odmítnuté uložení, přepnutí panelu i reload", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await createOnCanvas(page, "Deníkový uzel", { x: 200, y: 120 });
  await page.locator(".canvas-card").filter({ hasText: "Deníkový uzel" }).click();
  await page.getByRole("button", { name: "Otevřít vnitřní plátno", exact: true }).click();
  await page.getByRole("button", { name: "Mód: Text", exact: true }).click();
  const acceptSaves = await rejectSaves(page, "/api/node-journal");

  const journalTab = page.getByRole("tab", { name: "Deník", exact: true });
  const linksTab = page.getByRole("tab", { name: "Souvislosti", exact: true });
  const entry = page.getByTestId("journal-blocks").getByLabel("Zápis dne · blok 1");
  const status = page.getByTestId("journal-status");

  await journalTab.click();
  await entry.fill("Rozhodnutí, které se nesmí ztratit");
  await expect(status).toContainText("Neulož");

  // Rychlé přepnutí režimu panelu odpojí deník i s čekajícím uložením.
  await linksTab.click();
  await journalTab.click();
  await expect(entry).toHaveValue("Rozhodnutí, které se nesmí ztratit");
  await expect(status).toContainText("Neulož");

  await page.reload();
  await page.getByRole("tab", { name: "Deník", exact: true }).click();
  await expect(entry).toHaveValue("Rozhodnutí, které se nesmí ztratit");
  await expect(status).toContainText("Neulož");

  acceptSaves();
  await page.getByRole("button", { name: "Uložit zápis", exact: true }).click();
  await expect(status).toContainText("Uloženo · verze 1", { timeout: 8000 });
  await page.reload();
  await page.getByRole("tab", { name: "Deník", exact: true }).click();
  await expect(entry).toHaveValue("Rozhodnutí, které se nesmí ztratit");
});

test("skládání IME: Enter ani Tab během kompozice nemění strukturu bloků", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await createOnCanvas(page, "Kompozice", { x: 200, y: 120 });
  await page.locator(".canvas-card").filter({ hasText: "Kompozice" }).click();
  const outline = page.getByTestId("node-blocks");
  const first = outline.getByLabel("Bloky uzlu · blok 1");
  await first.fill("にほんご");

  const composed = (key: string) =>
    first.evaluate((el, value) => {
      el.dispatchEvent(
        new KeyboardEvent("keydown", { key: value, bubbles: true, composed: true, isComposing: true }),
      );
    }, key);

  await composed("Enter");
  await composed("Tab");
  await expect(outline.getByTestId("block-row")).toHaveCount(1);
  await expect(outline.getByTestId("block-row").first()).toHaveAttribute("data-depth", "0");
  await expect(first).toHaveValue("にほんご");

  // Po dokončení skládání tytéž klávesy strukturu mění: guard není vypnutá editace.
  await first.press("Enter");
  await expect(outline.getByTestId("block-row")).toHaveCount(2);
  await outline.getByLabel("Bloky uzlu · blok 2").press("Tab");
  await expect(outline.getByTestId("block-row").nth(1)).toHaveAttribute("data-depth", "1");
});
