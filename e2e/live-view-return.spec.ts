import { test, expect } from "@playwright/test";

// Reprodukce a regrese: v3 Live Run (Přehled a tickety <-> Dohled běhů) musí jít
// přepínat normálním kliknutím oběma směry, opakovaně, bez přetečení, na několika
// šířkách. Žádné API zápisy, žádný start modelu; jen skutečný izolovaný fixture projekt.
test("Live Run tabs switch back and forth with a normal click at several widths", async ({ page }) => {
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET" && new URL(request.url()).pathname.startsWith("/api/")) writes.push(request.url());
  });
  for (const width of [1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/?screen=canvas&project=draft&workspace=draft&environment=live&mode=agents");
    const overview = page.getByRole("region", { name: "Live workspace", exact: true });
    const advanced = page.getByRole("region", { name: "Agenti", exact: true });
    const overviewTab = page.getByRole("button", { name: "Přehled a tickety", exact: true });
    const runsTab = page.getByRole("button", { name: "Dohled běhů", exact: true });
    await expect(overview).toBeVisible();
    for (let i = 0; i < 2; i++) {
      await runsTab.click();
      await expect(advanced).toBeVisible();
      await expect(overview).toHaveCount(0);
      await expect(page.getByRole("toolbar", { name: "Nástroje Live Run" })).toBeVisible();
      await overviewTab.click();
      await expect(overview).toBeVisible();
      await expect(advanced).toHaveCount(0);
    }
    const columns = page.locator(".ns-columns");
    const sizes = await columns.evaluate((el) => ({ client: el.clientWidth, scroll: el.scrollWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.client + 2);
  }
  expect(writes).toEqual([]);
});
