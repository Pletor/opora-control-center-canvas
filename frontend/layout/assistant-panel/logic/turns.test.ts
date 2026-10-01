import { describe, expect, it } from "vitest";
import { addLocalUserMessage, applyEvent, emptyConversation, loadTranscript, type ChatItem } from "./assistant-events";
import { buildTurns, clockTime, decisionAnchor, formatDuration, lastAnswer, stepsSummary, turnLabel, turnMeta } from "./turns";

const history = (role: "user" | "assistant", text: string, id: string): ChatItem => ({ kind: "message", id, role, text, streaming: false, origin: "history" });

describe("skládání tahů", () => {
  it("tah = zpráva uživatele a všechno do další zprávy uživatele", () => {
    const conv = loadTranscript([
      { role: "user", text: "Otázka" },
      { role: "assistant", text: "První část" },
      { role: "assistant", text: "Druhá část" },
      { role: "user", text: "Další" },
      { role: "assistant", text: "Odpověď" },
    ]);
    const turns = buildTurns(conv.items);
    expect(turns.map((t) => [t.index, t.anchor, t.user?.text, t.entries.length])).toEqual([
      [1, "assistant-turn-1", "Otázka", 2],
      [2, "assistant-turn-2", "Další", 1],
    ]);
  });

  it("historie z přepisu nemá čas, délku ani kroky a hlavička je nevymýšlí", () => {
    const [turn] = buildTurns(loadTranscript([{ role: "user", text: "x" }, { role: "assistant", text: "y" }]).items);
    expect(turn).toMatchObject({ live: false, startedAt: null, durationMs: null, steps: null, ended: false });
    expect(turnMeta(turn)).toEqual([]);
  });

  it("živý tah nese čas odeslání, délku z turn_end a počet kroků", () => {
    const at = new Date(2026, 9, 1, 14, 2).getTime();
    let conv = addLocalUserMessage(emptyConversation(), "Najdi TopBar", "local-1", at);
    conv = [
      { seq: 1, type: "message", role: "user", text: "Najdi TopBar" },
      { seq: 2, type: "tool_use", id: "t1", name: "Grep", summary: "TopBar" },
      { seq: 3, type: "tool_result", id: "t1", ok: true, summary: "1 soubor" },
      { seq: 4, type: "tool_use", id: "t2", name: "Read", summary: "TopBar.tsx" },
      { seq: 5, type: "message", role: "assistant", text: "Je v TopBar.tsx." },
      { seq: 6, type: "turn_end", durationMs: 38_400, usage: {}, isError: false, numTurns: 3, denied: 1 },
    ].reduce(applyEvent, conv);
    const [turn] = buildTurns(conv.items);
    expect(turn).toMatchObject({ live: true, startedAt: at, durationMs: 38_400, steps: 2, denied: 1, ended: true });
    expect(turn.entries.map((e) => e.kind)).toEqual(["steps", "message"]);
    expect(turnMeta(turn)).toEqual(["14:02", "38 s", "2 kroky"]);
    expect(stepsSummary([turn])).toEqual({ steps: 2, denied: 1 });
  });

  it("živý tah bez nástrojů a bez délky ukáže jen to, co zná", () => {
    const conv = [{ seq: 1, type: "message", role: "user", text: "Ahoj" }, { seq: 2, type: "turn_end", durationMs: null, usage: {} }].reduce(applyEvent, emptyConversation());
    const [turn] = buildTurns(conv.items);
    expect(turn).toMatchObject({ live: true, startedAt: null, durationMs: null, steps: 0, ended: true });
    expect(turnMeta(turn)).toEqual([]);
  });

  it("text před první zprávou uživatele je tah bez zprávy", () => {
    const turns = buildTurns([history("assistant", "Vítejte", "a"), history("user", "Díky", "b")]);
    expect(turns.map((t) => [t.user?.text ?? null, turnLabel(t)])).toEqual([[null, "Začátek"], ["Díky", "Díky"]]);
    expect(buildTurns([])).toEqual([]);
  });

  it("souhrn kroků je null, když je všechno jen z historie", () => {
    expect(stepsSummary(buildTurns([history("user", "x", "a")]))).toBeNull();
  });
});

describe("popisky a kotvy", () => {
  it("osnova bere první slova zprávy a krátí na hranici slova", () => {
    const [turn] = buildTurns([history("user", "/grill-me Chci do OPORY přidat export plátna do PDF. Polož první kolo otázek.", "a")]);
    expect(turnLabel(turn)).toBe("/grill-me Chci do OPORY přidat export plátna do…");
    expect(turnLabel(turn, 200)).toBe("/grill-me Chci do OPORY přidat export plátna do PDF. Polož první kolo otázek.");
  });

  it("délka a čas česky", () => {
    expect([0, 38_400, 60_000, 125_000, 3_600_000, 3_840_000].map(formatDuration)).toEqual(["0 s", "38 s", "1 min", "2 min 5 s", "1 h", "1 h 4 min"]);
    expect(clockTime(new Date(2026, 9, 1, 9, 5).getTime())).toBe("9:05");
  });

  it("kotva otázky obsahuje jen povolené znaky", () => {
    expect(decisionAnchor("h1", "Q3")).toBe("assistant-q-h1-Q3");
    expect(decisionAnchor("msg:a b", "Q1")).toBe("assistant-q-msg_a_b-Q1");
  });

  it("poslední odpověď asistenta", () => {
    expect(lastAnswer([history("assistant", "a", "1"), history("user", "b", "2"), history("assistant", "c", "3"), history("assistant", "  ", "4")])?.id).toBe("3");
    expect(lastAnswer([history("user", "b", "2")])).toBeNull();
  });
});
