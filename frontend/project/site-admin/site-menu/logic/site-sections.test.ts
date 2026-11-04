import { expect, it } from "vitest";
import { readSiteSection, SITE_MENU, siteMenuItem } from "./site-sections";

it("lays out the menu of image9: settings, appearance, GDPR and the design system", () => {
  expect(SITE_MENU.map((group) => group.label)).toEqual(["Nastavení", "Vzhled", "GDPR", "Design System"]);
  expect(SITE_MENU[0].items.map((entry) => entry.label)).toEqual(["SEO", "Affiliate", "E-mail (SMTP)"]);
  expect(SITE_MENU[3].items.filter((entry) => entry.ready).map((entry) => entry.id))
    .toEqual(["overview", "colors", "typography", "spacing", "radius", "shadow", "files"]);
  expect(SITE_MENU[0].items.every((entry) => entry.ready)).toBe(true);
  expect(SITE_MENU[1].items.filter((entry) => entry.ready).map((entry) => entry.id)).toEqual(["appearance", "header", "footer", "buttons", "fonts"]);
  expect(siteMenuItem("cookies").ready).toBe(true);
});

it("reads the section from the address and falls back to the overview", () => {
  expect(readSiteSection("colors")).toBe("colors");
  expect(readSiteSection("seo")).toBe("seo");
  expect(readSiteSection("nope")).toBe("overview");
  expect(readSiteSection(null)).toBe("overview");
});
