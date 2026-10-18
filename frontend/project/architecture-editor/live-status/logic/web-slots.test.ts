import { describe, expect, it } from "vitest";
import type { WebHost } from "./web-status";
import { ALL_DOMAINS, emptyWeb, webFailed, webLoaded, webLoading, webLoadNotice, webSettled, webView } from "./web-slots";

const host = (domainId: string, over: Partial<WebHost> = {}): WebHost => ({ domainId, environment: "Produkce", host: domainId + ".cz", state: "up", httpStatus: 200, health: null, latencyMs: 50, checkedAt: "2026-10-14T10:03:00Z", detail: "", ...over });

describe("web po doménách", () => {
  it("načítání a chyba jedné domény se netýká ostatních", () => {
    let state = webLoaded(emptyWeb(), ALL_DOMAINS, [host("a"), host("b")], 1);
    state = webFailed(webLoading(state, "b"), "b", "síť", 2);
    expect(webView(state, "a")).toMatchObject({ error: "", loading: false, stale: "" });
    expect(webView(state, "b")).toMatchObject({ error: "síť", loading: false });
    expect(webView(state, "b").stale).toMatch(/^údaj z \d\d:\d\d, nepodařilo se obnovit$/);
    expect(webView(webLoading(state, "a"), "a").loading).toBe(true);
    expect(webView(webLoading(state, "a"), "b").loading).toBe(false);
  });
  it("novější úspěch domény přebije starší chybu celého projektu a naopak", () => {
    let state = webFailed(webLoaded(emptyWeb(), ALL_DOMAINS, [host("a")], 1), ALL_DOMAINS, "síť", 2);
    expect(webView(state, "a").error).toBe("síť");
    state = webLoaded(state, "a", [host("a")], 3);
    expect(webView(state, "a").error).toBe("");
    state = webFailed(webLoaded(state, "a", [host("a")], 4), "a", "timeout", 5);
    expect(webView(state, "a").error).toBe("timeout");
    state = webLoaded(state, ALL_DOMAINS, [host("a")], 6);
    expect(webView(state, "a").error).toBe("");
  });
  it("předběhnutý dotaz jen zhasne načítání", () => {
    const state = webSettled(webLoading(emptyWeb(), "a"), "a");
    expect(webView(state, "a")).toMatchObject({ loading: false, error: "", host: null });
  });
  it("první neúspěšné čtení přehledu řekne proč", () => {
    expect(webLoadNotice(webFailed(emptyWeb(), ALL_DOMAINS, "síť", 1))).toBe("Stav webu se nepodařilo načíst: síť");
    expect(webLoadNotice(webFailed(webLoaded(emptyWeb(), ALL_DOMAINS, [], 1), ALL_DOMAINS, "síť", 2))).toBe("");
  });
});
