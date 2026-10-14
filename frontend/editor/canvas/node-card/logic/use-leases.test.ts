import { expect, it } from "vitest";
import { leasesUnchanged, type CardLease } from "./use-leases";

const lease = (offset: number, over: Partial<CardLease> = {}): CardLease => ({ owner: "a", expiresAt: 100, active: true, serverOffset: offset, ...over });

it("posun hodin o zlomek sekundy nemění pronájmy", () => {
  expect(leasesUnchanged({ n: lease(1) }, { n: lease(1.4) })).toBe(true);
});
it("změna majitele, expirace, počtu nebo velkého posunu je změna", () => {
  expect(leasesUnchanged({ n: lease(1) }, { n: lease(1, { owner: "b" }) })).toBe(false);
  expect(leasesUnchanged({ n: lease(1) }, { n: lease(1, { expiresAt: 101 }) })).toBe(false);
  expect(leasesUnchanged({ n: lease(1) }, { n: lease(1), m: lease(1) })).toBe(false);
  expect(leasesUnchanged({ n: lease(1) }, { n: lease(5) })).toBe(false);
});
