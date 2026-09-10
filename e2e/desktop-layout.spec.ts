import { test, expect } from "@playwright/test";

for (const width of [1280, 1440, 1920]) {
  test(`desktop ${width}: all environments fit and expose separate tools`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/?screen=canvas&project=draft&workspace=draft&mode=structure");
    const nav = page.getByRole("navigation", { name: "Pracovní prostředí" });
    for (const [label, tools, slug] of [["Projekt", "Nástroje Projektu", "project"], ["Editor", "Nástroje Editoru", "editor"], ["Live Run", "Nástroje Live Run", "live"]]) {
      await nav.getByRole("button", { name: label, exact: true }).click();
      if (slug === "live") {
        // Nový výchozí region Live workspace, teprve klik na Dohled běhů odkryje starý panel s nástroji.
        await expect(page.getByRole("region", { name: "Live workspace", exact: true })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        await page.screenshot({ path: `evidence/desktop-v3-live-${width}.png`, fullPage: true });
        await page.getByRole("button", { name: "Dohled běhů", exact: true }).click();
      }
      await expect(page.getByRole("toolbar", { name: tools, exact: true })).toBeVisible();
      if (slug === "project") await expect(page.getByLabel("Podstata", { exact: true })).toBeVisible();
      if (slug === "editor") await expect(page.locator(".react-flow")).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const bounds = await nav.boundingBox();
      expect(bounds?.x).toBeGreaterThanOrEqual(0);
      expect((bounds?.x ?? 0) + (bounds?.width ?? 0)).toBeLessThanOrEqual(width);
      await page.screenshot({ path: `evidence/desktop-v2-${slug}-${width}.png`, fullPage: true });
    }
    expect(errors).toEqual([]);
  });
}
