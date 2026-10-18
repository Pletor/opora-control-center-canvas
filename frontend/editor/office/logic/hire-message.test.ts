import { describe, expect, it } from "vitest";
import { TITLE_MAX, hireDraft, hireRequest, hireTitle } from "./hire-message";

describe("hire-message", () => {
  it("karta: zpráva podle kontraktu §3.3", () => {
    expect(hireDraft({ kind: "node", id: "c1", name: "Login" })).toBe(
      "Pracuj na kartě «Login» (`c1`). Načti `node-brief`, drž se cíle a akceptace, výsledek dej jako `agent-output` přes skill opora-control-center.",
    );
  });

  it("sektor: zpráva podle kontraktu §3.3", () => {
    expect(hireDraft({ kind: "sector", id: "s1", name: "Auth" })).toBe(
      "Jsi v sektoru «Auth» (`s1`). Přečti jeho cíl, akceptaci a bránu; navrhni další krok (rozklad na karty / shrnutí podnětů / kritika), nic nezapisuj bez schválení.",
    );
  });

  it("název relace: karta svým jménem, sektor s předponou, prázdné jméno náhradou", () => {
    expect(hireTitle({ kind: "node", id: "c1", name: " Login " })).toBe("Login");
    expect(hireTitle({ kind: "sector", id: "s1", name: "Auth" })).toBe("Sektor: Auth");
    expect(hireTitle({ kind: "node", id: "c1", name: "" })).toBe("Nepojmenovaná karta");
  });

  it("název relace má nejvýš 60 znaků", () => {
    const title = hireTitle({ kind: "sector", id: "s1", name: "x".repeat(100) });
    expect(title.length).toBe(TITLE_MAX);
    expect(title.startsWith("Sektor: x")).toBe(true);
  });

  it("žádost nese vazbu jen na kartu, nebo jen na sektor, a předvyplněnou zprávu", () => {
    expect(hireRequest({ kind: "node", id: "c1", name: "Login" }, "main")).toEqual({
      workspace: "main", nodeId: "c1", sectorId: null, title: "Login", draft: hireDraft({ kind: "node", id: "c1", name: "Login" }),
    });
    const sector = hireRequest({ kind: "sector", id: "s1", name: "Auth" }, "wt");
    expect([sector.workspace, sector.nodeId, sector.sectorId, sector.title]).toEqual(["wt", null, "s1", "Sektor: Auth"]);
  });
});
