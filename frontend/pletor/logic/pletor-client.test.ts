import { afterEach, describe, expect, it, vi } from "vitest";
import {
  actionLabel, brainLabel, brainText, escalationText, fetchPletorLlm, fetchPletorState, heartText, parseBrain, sendPletorMessage, sendPletorMessageStream, setPletorBrain,
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

  it("proud: delty jdou hned ven, řádek NDJSON přes hranici kousků se složí, výsledek je done", async () => {
    const parts = ['{"type":"delta","text":"Dobrý "}\n{"type":"del', 'ta","text":"den."}\n', '{"type":"done","reply":"Dobrý den!","actions":[{"type":"vault_note","text":"x","ok":true}]}\n'];
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      const body = new ReadableStream({ start(controller) { for (const part of parts) controller.enqueue(new TextEncoder().encode(part)); controller.close(); } });
      return { ok: true, status: 200, body, text: async () => "{}", headers: { get: () => null } };
    });
    const deltas: string[] = [];
    const result = await sendPletorMessageStream("p1", "main", "Ahoj", true, (text) => deltas.push(text));
    const write = calls.find((call) => call.init?.method === "POST")!;
    expect(write.url).toBe("/api/pletor/messages/stream");
    expect(JSON.parse(String(write.init!.body))).toEqual({ project: "p1", workspace: "main", text: "Ahoj", voice: true });
    expect(deltas).toEqual(["Dobrý ", "den."]);
    expect(result).toEqual({ reply: "Dobrý den!", actions: [{ type: "vault_note", text: "x", ok: true }] });
  });

  it("proud: HTTP chyba nese hlášku serveru, proud bez done je selhání", async () => {
    vi.stubGlobal("fetch", async () => ({ ok: false, status: 503, body: null, text: async () => '{"error":"Pletor spí."}', headers: { get: () => null } }));
    await expect(sendPletorMessageStream("p1", "main", "Ahoj", true, () => undefined)).rejects.toThrow("Pletor spí.");
    vi.stubGlobal("fetch", async () => ({ ok: true, status: 200, body: new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode('{"type":"delta","text":"A"}\n')); c.close(); } }), headers: { get: () => null } }));
    await expect(sendPletorMessageStream("p1", "main", "Ahoj", true, () => undefined)).rejects.toThrow(/bez done/);
  });

  it("hlasová zpráva nese voice: true", async () => {
    const calls = stubFetch({ reply: "Ano.", actions: [] });
    await sendPletorMessage("p1", "main", "Jak to jde", true);
    expect(JSON.parse(String(calls.find((call) => call.init?.method === "POST")!.init!.body))).toEqual({ project: "p1", workspace: "main", text: "Jak to jde", voice: true });
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
    expect(await fetchPletorState("p", "w")).toEqual({ messages: [], heart: null, escalations: [], brain: { brain: "claude", model: null, available: [] } });
  });

  it("mozek ze stavu: ollama s modelem, cokoli jiného je claude", () => {
    const local = parseBrain({ brain: "ollama", model: "qwen3:14b", available: ["qwen3:14b", 3] });
    expect(local).toEqual({ brain: "ollama", model: "qwen3:14b", available: ["qwen3:14b"] });
    expect(brainText(local)).toBe("ollama · qwen3:14b");
    expect(brainText(parseBrain({ brain: "claude", model: "sonnet" }))).toBe("claude");
    expect(brainText(parseBrain({ brain: "gpt" }))).toBe("claude");
    expect(brainText(parseBrain(null))).toBe("claude");
    expect(parseBrain({ brain: "claude", model: "sonnet", available: ["qwen3:14b"] })).toEqual({ brain: "claude", model: "sonnet", available: ["qwen3:14b"] });
  });

  it("přepne mozek přes POST /api/pletor/brain a vrátí nový stav i důvod selhání", async () => {
    const calls = stubFetch({ ok: false, reply: "Ollama nemá model.", brain: { brain: "claude", model: "sonnet", available: [] } });
    const result = await setPletorBrain("ollama");
    const write = calls.find((call) => call.init?.method === "POST")!;
    expect(write.url).toBe("/api/pletor/brain");
    expect(JSON.parse(String(write.init!.body))).toEqual({ brain: "ollama" });
    expect(result).toEqual({ ok: false, reply: "Ollama nemá model.", brain: { brain: "claude", model: "sonnet", available: [] } });
  });
});

describe("nastavení LLM", () => {
  it("čte GET /api/pletor/llm a doplní chybějící sekce", async () => {
    const calls = stubFetch({ claude: { available: true, model: "opus" }, cswap: { available: false, installHint: "uv tool install claude-swap" } });
    const llm = await fetchPletorLlm();
    expect(calls[0].url).toBe("/api/pletor/llm");
    expect(calls[0].init?.method ?? "GET").toBe("GET");
    expect(llm.claude).toMatchObject({ available: true, model: "opus" });
    expect(llm.codex).toMatchObject({ available: false, reason: "Server sekci nevrátil." });
    expect(llm.cswap.installHint).toBe("uv tool install claude-swap");
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

  it("brainLabel: Claude je cloud na předplatném, Ollama lokální zdarma", () => {
    expect(brainLabel(parseBrain({ brain: "claude", model: "sonnet" }))).toEqual({ name: "Claude Sonnet 5.5", plan: "cloud · předplatné", local: false });
    expect(brainLabel(parseBrain(undefined)).name).toBe("Claude Sonnet 5.5");
    expect(brainLabel(parseBrain({ brain: "ollama", model: "qwen3:14b" }))).toEqual({ name: "qwen3:14b", plan: "lokální · zdarma", local: true });
  });
});
