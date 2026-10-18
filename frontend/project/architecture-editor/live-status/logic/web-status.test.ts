import { describe, expect, it } from "vitest";
import { applyHosts, badgeText, badgeTitle, hostOf, normalizeWebStatus, refreshTitle, refreshWait, WEB_STATE, webStaleNote, type WebHost } from "./web-status";

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
  it("odpověď jedné domény nahradí všechny její hosty, jiné domény nechá", () => {
    const prev = [host({ host: "a.cz", domainId: "a" }), host({ host: "b.cz", domainId: "b" }), host({ host: "stary.b.cz", domainId: "b" })];
    const merged = applyHosts(prev, [host({ host: "b.cz", domainId: "b", state: "unreachable" })], "b");
    expect(merged.map((item) => `${item.host}:${item.state}`)).toEqual(["a.cz:up", "b.cz:unreachable"]);
    expect(hostOf(merged, "b")?.state).toBe("unreachable");
    expect(hostOf(merged, "x")).toBeNull();
  });
  it("plná odpověď nahradí celý seznam", () => {
    expect(applyHosts([host({ host: "a.cz", domainId: "a" })], [host({ host: "c.cz", domainId: "c" })], null).map((item) => item.host)).toEqual(["c.cz"]);
  });
  it("ruční ověření nejdřív 30 s po kontrole hostu", () => {
    const now = Date.parse("2026-10-14T12:00:00Z");
    expect(refreshWait("2026-10-14T11:59:48Z", now)).toBe(18);
    expect(refreshWait("2026-10-14T11:59:48", now)).toBe(18);
    expect(refreshWait("2026-10-14T11:59:00Z", now)).toBe(0);
    expect(refreshWait("2026-10-14T12:05:00Z", now)).toBe(30);
    expect(refreshWait(null, now)).toBe(0);
    expect(refreshTitle(18)).toBe("Další ověření za 18 s");
    expect(refreshTitle(0)).toContain("Ověří host znovu");
  });
  it("zastaralý web nese čas kontroly hostu, jen když obnovení selhalo", () => {
    const checked = host({ checkedAt: "2026-10-14T10:03:00Z" });
    const clock = new Date(Date.parse("2026-10-14T10:03:00Z"));
    const hhmm = `${String(clock.getHours()).padStart(2, "0")}:${String(clock.getMinutes()).padStart(2, "0")}`;
    expect(webStaleNote(checked, true)).toBe(`údaj z ${hhmm}, nepodařilo se obnovit`);
    expect(webStaleNote(checked, false)).toBe("");
    expect(webStaleNote(host({}), true)).toBe("");
  });
});
