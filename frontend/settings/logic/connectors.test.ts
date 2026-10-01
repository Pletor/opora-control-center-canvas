import { describe, expect, it } from "vitest";
import {
  CONNECTORS,
  CONNECTOR_STATUS_LABEL,
  OPENVIKING_ID,
  memoryConnector,
  memorySettingsPayload,
  provisionPayload,
  provisionResultSummary,
} from "./connectors";

describe("connectors: katalog", () => {
  it("OpenViking je v seznamu a jeho stav se čte ze serveru, ne z kódu", () => {
    const openviking = CONNECTORS.find((item) => item.id === OPENVIKING_ID);
    expect(openviking?.name).toBe("OpenViking – paměť rolí");
    expect(openviking?.status).toBe("live");
  });

  it("ostatní konektory zůstávají připravované", () => {
    expect(CONNECTORS.filter((item) => item.id !== OPENVIKING_ID).every((item) => item.status === "planned")).toBe(true);
  });

  it("každý stav má popisek a každý konektor jméno i větu k čemu je", () => {
    for (const item of CONNECTORS) {
      expect(item.name.length).toBeGreaterThan(0);
      expect(item.purpose.length).toBeGreaterThan(0);
      expect(CONNECTOR_STATUS_LABEL[item.status].length).toBeGreaterThan(0);
    }
  });

  it("id konektorů jsou jedinečná", () => {
    expect(new Set(CONNECTORS.map((item) => item.id)).size).toBe(CONNECTORS.length);
  });
});

describe("connectors: živý stav paměti rolí", () => {
  it("nenačtený stav není vypnuto, ale nevědomost, a nedá se přepínat", () => {
    const view = memoryConnector(null);
    expect(view.label).toBe("Zjišťuji…");
    expect(view.enabled).toBe(false);
    expect(view.busy).toBe(true);
  });

  it("běžící paměť nabídne vypnutí a ukáže adresu serveru", () => {
    const view = memoryConnector({ status: "configured", reason: "OpenViking odpovídá na loopbacku.", url: "http://127.0.0.1:1933" });
    expect(view).toMatchObject({ label: "K dispozici", tone: "available", enabled: true, action: "Vypnout", next: false, busy: false });
    expect(view.detail).toBe("OpenViking odpovídá na loopbacku. (http://127.0.0.1:1933)");
  });

  it("nedostupný server je porucha, ne vypnutý přepínač", () => {
    const view = memoryConnector({ status: "unavailable", reason: "Spojení odmítnuto." });
    expect(view).toMatchObject({ label: "Nedostupné", tone: "error", enabled: true, action: "Vypnout", next: false });
    expect(view.detail).toBe("Spojení odmítnuto.");
  });

  it("vypnutá paměť nabídne zapnutí a nese důvod ze serveru", () => {
    const view = memoryConnector({ status: "disabled", reason: "Paměť rolí je v nastavení aplikace vypnutá." });
    expect(view).toMatchObject({ label: "Vypnuto", tone: "planned", enabled: false, action: "Zapnout", next: true, busy: false });
    expect(view.detail).toBe("Paměť rolí je v nastavení aplikace vypnutá.");
  });

  it("neznámý stav se přizná, nevydává se za běžící paměť", () => {
    expect(memoryConnector({ status: "vymysleno" })).toMatchObject({ label: "Neznámý stav", tone: "error", busy: true });
  });

  it("přepnutí posílá právě jedno pole", () => {
    expect(memorySettingsPayload(true)).toEqual({ enabled: true });
    expect(Object.keys(memorySettingsPayload(false))).toEqual(["enabled"]);
  });

  it("role bez klíče je needs_provisioning, ne porucha ani vypnuto", () => {
    const view = memoryConnector({
      status: "needs_provisioning", reason: "Bez klíče zůstávají role: role-db.",
      url: "http://127.0.0.1:1933", missingRoles: ["role-db"],
    });
    expect(view).toMatchObject({ label: "Vyžaduje založení rolí", tone: "needs_provisioning", enabled: true, busy: false });
    expect(view.detail).toBe("Bez klíče zůstávají role: role-db. (http://127.0.0.1:1933)");
    expect(view.missingRoles).toEqual(["role-db"]);
  });

  it("ostatní stavy nemají žádné chybějící role", () => {
    expect(memoryConnector({ status: "configured" }).missingRoles).toEqual([]);
    expect(memoryConnector(null).missingRoles).toEqual([]);
  });

  it("cizí tvar missingRoles se čte jako žádné role", () => {
    expect(memoryConnector({ status: "needs_provisioning", missingRoles: "role-db" as never }).missingRoles).toEqual([]);
  });
});

describe("connectors: rozdání klíčů rolím", () => {
  it("tělo nese jen výslovné potvrzení", () => {
    expect(provisionPayload()).toEqual({ confirmed: true });
    expect(Object.keys(provisionPayload())).toEqual(["confirmed"]);
  });

  it("bez odpovědi není co shrnovat", () => {
    expect(provisionResultSummary(null)).toBe("");
  });

  it("shrnutí jmenuje založené, beze změny i chyby", () => {
    const summary = provisionResultSummary({
      status: "partial", provisioned: ["role-frontend"], reused: ["role-db"],
      errors: [{ role: "role-x", reason: "OpenViking není dostupný." }],
    });
    expect(summary).toBe(
      "Založeno: role-frontend. Beze změny: role-db. Nepodařilo se: role-x (OpenViking není dostupný.).",
    );
  });

  it("žádná změna dostane vlastní větu, ne prázdný řetězec", () => {
    expect(provisionResultSummary({ status: "configured", provisioned: [], reused: [], errors: [] }))
      .toBe("Rozdání klíčů rolím neudělalo žádnou změnu.");
  });
});
