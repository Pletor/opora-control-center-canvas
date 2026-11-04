import { expect, it } from "vitest";
import { ctaProblem, ctaView, EMPTY_HEADER, headerClass, navItems, readHeader, SAMPLE_PAGES } from "./header";

it("reads the header with defaults", () => {
  expect(readHeader({})).toEqual(EMPTY_HEADER);
  expect(readHeader({ header: { sticky: true, cta: { label: "Rezervace" } } }).cta).toEqual({ ...EMPTY_HEADER.cta, label: "Rezervace" });
});

it("builds menu items from pages or the manual list", () => {
  const extra = { label: "Blog", pageId: "", url: "https://blog.example.cz" };
  expect(navItems({ ...EMPTY_HEADER, items: [extra] })).toEqual([...SAMPLE_PAGES, extra]);
  expect(navItems({ ...EMPTY_HEADER, nav: "manual", items: [extra, { label: " ", pageId: "", url: "/" }] })).toEqual([extra]);
  expect(SAMPLE_PAGES.map((page) => page.pageId)).toEqual(["uvod", "sluzby", "o-nas", "kontakt"]);
});

it("maps settings to BEM classes and the CTA button", () => {
  expect(headerClass({ ...EMPTY_HEADER, variant: "centered", sticky: true })).toBe("ds-header ds-header--centered ds-header--sticky");
  const cta = { label: "Rezervace", pageId: "rezervace", url: "", variant: "ghost" };
  expect(ctaView({ ...EMPTY_HEADER, cta }, ["primary"])).toEqual({ show: true, className: "ds-btn ds-btn--sm ds-btn--primary", href: "/rezervace" });
  expect(ctaView(EMPTY_HEADER, []).show).toBe(false);
  expect(ctaProblem({ ...EMPTY_HEADER, cta: { ...cta, pageId: "" } })).toMatch("cíl");
});
