import { describe, expect, it } from "vitest";
import type { SiteSettings } from "@/shared/types/logic/types";
import { SITE_GROUPS, filledCount, siteValue, withSiteValue } from "./site-settings";

const empty = (): SiteSettings => ({
  seo: { titleTemplate: "", description: "", ogImage: "" },
  legal: { gdprContact: "", cookies: "" },
  email: { from: "", replyTo: "" },
  design: { header: "", footer: "", buttons: "", typography: { h1: "", h2: "", h3: "", h4: "", h5: "", body: "", fonts: "" } },
});

describe("site-settings – pole nastavení webu", () => {
  it("každé pole editoru míří na existující pole nastavení", () => {
    const site = empty();
    for (const group of SITE_GROUPS) for (const field of group.fields) {
      expect(siteValue(withSiteValue(site, field.path, "x"), field.path)).toBe("x");
    }
    expect(SITE_GROUPS.flatMap((group) => group.fields)).toHaveLength(17);
  });

  it("změna jednoho pole nemění ostatní ani původní objekt", () => {
    const site = empty();
    const next = withSiteValue(site, "design.typography.h1", "Fraunces 48");
    expect(next.design.typography.h1).toBe("Fraunces 48");
    expect(site.design.typography.h1).toBe("");
    expect(next.seo).toBe(site.seo);
    expect(next.design.header).toBe("");
  });

  it("počítá vyplněná pole skupiny", () => {
    const design = SITE_GROUPS.find((group) => group.id === "design")!;
    const site = withSiteValue(withSiteValue(empty(), "design.header", "logo vlevo"), "design.footer", "  ");
    expect(filledCount(site, design)).toBe(1);
  });
});
