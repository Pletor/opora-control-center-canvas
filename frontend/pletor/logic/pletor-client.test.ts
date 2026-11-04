import { afterEach, describe, expect, it, vi } from "vitest";
import {
  actionLabel, escalationText, fetchPletorState, heartText, PLETOR_PREFS_KEY, readPletorOpen, sendPletorMessage, writePletorOpen,
} from "./pletor-client";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(body: unknown) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return { ok: true, status: 200, text: async () => JSON.stringify(body), headers: { get: () => null } };
  });
  return calls;
}

describe("volání Pletora", () => {
  it("pošle zprávu s projektem a prostorem a vrátí odpověď s akcemi", async () => {
    const calls = stubFetch({ reply: "Předám srdci.", actions: [{ type: "heart_message", text: "záměr", ok: true }, { bad: 1 }] });
    const result = await sendPletorMessage("p1", "main", "Chci přihlášení");
    const write = calls.find((call) => call.init?.method === "POST")!;
    expect(write.url).toBe("/api/pletor/messages");
    expect(JSON.parse(String(write.init!.body))).toEqual({ project: "p1", workspace: "main", text: "Chci přihlášení" });
    expect(result).toEqual({ reply: "Předám srdci.", actions: [{ type: "heart_message", text: "záměr", ok: true }] });
  });

  it("načte stav a zahodí zprávy s neznámou rolí", async () => {
    const calls = stubFetch({
      messages: [{ role: "human", text: "a", at: "t" }, { role: "system", text: "x", at: "t" }, { role: "pletor", text: "b", at: "t" }],
      heart: "Spí", escalations: [{}, {}],
    });
    const state = await fetchPletorState("p 1", "ws");
    expect(calls[0].url).toBe("/api/pletor/state?project=p%201&workspace=ws");
    expect(state.messages.map((m) => m.role)).toEqual(["human", "pletor"]);
    expect(state.escalations).toHaveLength(2);
    expect(state.heart).toBe("Spí");
  });

  it("chybějící pole jsou prázdná", async () => {
    stubFetch({});
    expect(await fetchPletorState("p", "w")).toEqual({ messages: [], heart: null, escalations: [] });
  });
});

describe("mapování pro okno", () => {
  it("stav srdce jednou větou", () => {
    expect(heartText("Pracuje")).toBe("Pracuje");
    expect(heartText({ state: "spí" })).toBe("spí");
    expect(heartText({ enabled: true, running: true, pending: 0, batches: [], sleeping: false, sleepingUntil: null, nextAllowedAt: null, error: null })).toBe("Pracuje na dávce");
    expect(heartText(null)).toBe("Stav srdce neznámý");
  });

  it("počet eskalací česky", () => {
    expect(escalationText(0)).toBe("žádná eskalace");
    expect(escalationText(1)).toBe("1 čekající eskalace");
    expect(escalationText(3)).toBe("3 čekající eskalace");
    expect(escalationText(7)).toBe("7 čekajících eskalací");
  });

  it("chip akce", () => {
    expect(actionLabel({ type: "heart_message", text: "x", ok: true })).toEqual({ ok: true, text: "Poslal jsem srdci" });
    expect(actionLabel({ type: "vault_note", text: "x", ok: true })).toEqual({ ok: true, text: "Zapsal do Schránky" });
    expect(actionLabel({ type: "vault_note", text: "x", ok: false, detail: "revize" })).toEqual({ ok: false, text: "Selhalo: revize" });
  });
});

describe("otevřenost okna", () => {
  it("ukládá se jedním klíčem pro aplikaci", () => {
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => store.set(k, v) });
    expect(readPletorOpen()).toBe(false);
    writePletorOpen(true);
    expect(store.get(PLETOR_PREFS_KEY)).toBe('{"open":true}');
    expect(readPletorOpen()).toBe(true);
    store.set(PLETOR_PREFS_KEY, "{poškozené");
    expect(readPletorOpen()).toBe(false);
  });
});
