import { expect, it } from "vitest";
import { EMPTY_FOOTER, footerAdvice, footerClass, legalLine, readFooter, socialProblem } from "./footer";

it("reads the footer with defaults", () => {
  expect(readFooter({})).toEqual(EMPTY_FOOTER);
  expect(readFooter({ footer: { variant: "simple", cookieLink: false } })).toEqual({ ...EMPTY_FOOTER, variant: "simple", cookieLink: false });
});

it("maps variant, legal year and advice", () => {
  expect(footerClass({ ...EMPTY_FOOTER, variant: "centered" })).toBe("ds-footer ds-footer--centered");
  expect(legalLine("© {rok} Ember s.r.o.", 2026)).toBe("© 2026 Ember s.r.o.");
  expect(legalLine("", 2026)).toMatch("2026");
  expect(footerAdvice({ ...EMPTY_FOOTER, columns: [{ title: "A", links: [] }] })).toMatch("právní");
  expect(footerAdvice(EMPTY_FOOTER)).toBe("");
});

it("checks social links like the server", () => {
  expect(socialProblem({ name: "x", url: "http://x.com/e" })).not.toBe("");
  expect(socialProblem({ name: "x", url: "https://x.com/e" })).toBe("");
});
