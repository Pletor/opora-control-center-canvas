import { describe, expect, it } from "vitest";
import { badgeText, badgeTitle, hostOf, mergeHosts, normalizeWebStatus, WEB_STATE, type WebHost } from "./web-status";

const host = (over: Partial<WebHost>): WebHost => ({ domainId: "d1", environment: "Produkce", host: "www.example.cz", state: "up", httpStatus: 200, health: null, latencyMs: 120.4, checkedAt: null, detail: "", ...over });

describe("stav webu", () => {
  it("normalizuje odpověď a neznámý stav čte jako neověřeno", () => {
    const hosts = normalizeWebStatus({ hosts: [{ domainId: "d1", host: "a.cz", state: "weird" }, { domainId: "d2" }] });
    expect(hosts).toHaveLength(1);
    expect(hosts[0]).toMatchObject({ host: "a.cz", state: "unchecked", httpStatus: null, latencyMs: null });
    expect(normalizeWebStatus(null)).toEqual([]);
  });
  it("žeton nese slovo a u běžícího webu i latenci", () => {
    expect(badgeText(host({}))).toBe("běží · 120 ms");
    expect(badgeText(host({ state: "dns_missing", latencyMs: null }))).toBe("DNS neexistuje");
    expect(badgeText(null)).toBe("neověřeno");
  });
  it("chybějící DNS je neutrální, ne chyba", () => {
    expect(WEB_STATE.dns_missing.tone).toBe("neutral");
    expect(WEB_STATE.dns_no_web.tone).toBe("neutral");
    expect(WEB_STATE.unreachable.tone).toBe("bad");
  });
  it("title vysvětlí kód, health a podrobnost", () => {
    expect(badgeTitle(host({ health: "ok", detail: "přesměrování" }))).toBe("www.example.cz · běží · HTTP 200 · health ok · přesměrování");
    expect(badgeTitle(null)).toBe("Web ještě nebyl ověřen.");
  });
  it("výsledek jedné domény přepíše jen její host", () => {
    const merged = mergeHosts([host({ host: "a.cz", domainId: "a" }), host({ host: "b.cz", domainId: "b" })], [host({ host: "b.cz", domainId: "b", state: "unreachable" })]);
    expect(merged.map((item) => `${item.host}:${item.state}`)).toEqual(["a.cz:up", "b.cz:unreachable"]);
    expect(hostOf(merged, "b")?.state).toBe("unreachable");
    expect(hostOf(merged, "x")).toBeNull();
  });
});
