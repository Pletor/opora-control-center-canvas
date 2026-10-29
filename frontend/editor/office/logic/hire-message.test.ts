import { describe, expect, it } from "vitest";
import { hireRequest, hireText } from "./hire-message";

describe("hire-message", () => {
  it("karta: srdce má posadit pracovníka podle node-brief", () => {
    expect(hireText({ kind: "node", id: "c1", name: " Login " })).toBe(
      "Posaď pracovníka ke kartě «Login» (`c1`): zadej úkol podle jejího `node-brief` (cíl a akceptace).",
    );
  });

  it("sektor: srdce má sektor projít a navrhnout další krok", () => {
    expect(hireText({ kind: "sector", id: "s1", name: "Auth" })).toBe(
      "Projdi sektor «Auth» (`s1`): přečti jeho cíl, akceptaci a bránu a navrhni další krok (rozklad na karty / shrnutí podnětů / kritika).",
    );
  });

  it("prázdné jméno dostane náhradu", () => {
    expect(hireText({ kind: "node", id: "c1", name: "" })).toContain("«Nepojmenovaná karta»");
    expect(hireText({ kind: "sector", id: "s1", name: " " })).toContain("«Nepojmenovaný sektor»");
  });

  it("žádost nese prostor a text", () => {
    expect(hireRequest({ kind: "node", id: "c1", name: "Login" }, "wt")).toEqual({
      workspace: "wt", text: hireText({ kind: "node", id: "c1", name: "Login" }),
    });
  });
});
