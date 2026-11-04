import { expect, it } from "vitest";
import { acceptAll, barClass, EMPTY_GDPR, gdprAdvice, info, initialConsent, readGdpr, toggleConsent, withCategory } from "./cookie-bar";

const bar = EMPTY_GDPR.cookieBar;

it("reads gdpr with defaults and keeps custom category texts", () => {
  expect(readGdpr({})).toEqual(EMPTY_GDPR);
  const read = readGdpr({ gdpr: { cookieBar: { enabled: true, categoryInfo: { analytics: { label: "Měření" } } } } });
  expect(read.cookieBar.categoryInfo).toEqual({ analytics: { label: "Měření" } });
  expect(info(read.cookieBar, "analytics").label).toBe("Měření");
  expect(info(read.cookieBar, "marketing").label).toBe("Marketingové");
});

it("keeps necessary always on and categories in fixed order", () => {
  const withBoth = withCategory(withCategory(bar, "marketing", true), "analytics", true);
  expect(withBoth.categories).toEqual(["necessary", "analytics", "marketing"]);
  expect(withCategory(withBoth, "necessary", false).categories).toContain("necessary");
  const dropped = withCategory({ ...withBoth, categoryInfo: { marketing: { label: "M", description: "" } } }, "marketing", false);
  expect(dropped.categories).toEqual(["necessary", "analytics"]);
  expect(dropped.categoryInfo).toEqual({});
});

it("starts with rejection and lets the visitor toggle everything but necessary", () => {
  const consent = initialConsent();
  expect(Object.values(consent).filter(Boolean)).toHaveLength(1);
  expect(toggleConsent(consent, "necessary").necessary).toBe(true);
  expect(toggleConsent(consent, "analytics").analytics).toBe(true);
  expect(acceptAll(withCategory(bar, "analytics", true))).toEqual({ necessary: true, preferences: false, analytics: true, marketing: false });
});

it("maps position to BEM and gives the server's advice", () => {
  expect(barClass({ ...bar, position: "bottom-left" })).toBe("ds-cookie-bar ds-cookie-bar--bottom-left");
  expect(gdprAdvice(EMPTY_GDPR)).toEqual([]);
  expect(gdprAdvice({ ...EMPTY_GDPR, cookieBar: { ...bar, enabled: true, consentDays: 700 } })).toHaveLength(4);
});
