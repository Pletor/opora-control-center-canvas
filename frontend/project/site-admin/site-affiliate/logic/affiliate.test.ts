import { expect, it } from "vitest";
import { attributionText, EMPTY_AFFILIATE, paramProblem, partnerLink, programProblem, readAffiliate } from "./affiliate";

it("reads affiliate with defaults", () => {
  expect(readAffiliate({})).toEqual(EMPTY_AFFILIATE);
  expect(readAffiliate({ affiliate: { enabled: true, programs: [{ name: "Heureka" }] } }).programs).toHaveLength(1);
});

it("checks param and programs like the server", () => {
  expect(paramProblem("Ref Code")).not.toBe("");
  expect(paramProblem("partner_id")).toBe("");
  expect(programProblem({ name: "", url: "", commission: "", code: "" })).toMatch("jméno");
  expect(programProblem({ name: "A", url: "http://a.cz", commission: "", code: "" })).toMatch("https");
  expect(programProblem({ name: "A", url: "https://a.cz", commission: "5 %", code: "" })).toBe("");
});

it("builds a partner link and explains attribution", () => {
  expect(partnerLink("ember.cz", "ref", "KAVA 1")).toBe("https://ember.cz/?ref=KAVA+1");
  expect(partnerLink("", "", "")).toBe("https://www.example.cz/?ref=PARTNER");
  expect(partnerLink("bad host/", "ref", "A")).toBe("https://www.example.cz/?ref=A");
  expect(attributionText({ ...EMPTY_AFFILIATE, attribution: "first", cookieDays: 7 })).toMatch("první partner");
});
