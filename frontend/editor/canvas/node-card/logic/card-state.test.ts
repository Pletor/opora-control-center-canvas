import { describe, expect, it } from "vitest";
import { cardState, sinceLabel } from "./card-state";
import type { CardProcessView, ProcessDot } from "./card-process";
import type { WorkRow } from "./use-work-overview";

const dot = (id: string, over: Partial<ProcessDot> = {}): ProcessDot => ({
  id, kind: "work", lens: "", status: "todo", current: false, stuck: false, retry: false, title: id, note: "", doneBy: "", ...over,
});
const process = (dots: ProcessDot[], over: Partial<CardProcessView> = {}): CardProcessView => ({
  routed: dots.length > 0, profile: "code", profileLabel: "Kód", dots, finished: 0, total: dots.length, waitingOnHuman: false, proposed: 0, proofs: [], ...over,
});
const work = (over: Partial<WorkRow> = {}): WorkRow => ({
  id: "n", name: "Karta", status: "waiting", agent: "", startedAt: null, lastActivity: null, touched: null, waitingOnHuman: [], blockedBy: [], ...over,
});
const base = { closed: false, doneProposed: false };

describe("cardState", () => {
  it("puts a stuck stage first, then a question, then a proposal, then a blocker", () => {
    const stuck = process([dot("h", { kind: "critic", lens: "hacker", status: "failed", stuck: true, title: "Kritik: útok", note: "únik tokenu" })]);
    expect(cardState({ ...base, doneProposed: true, process: stuck, work: work({ blockedBy: [{ id: "x", name: "X" }] }) }))
      .toMatchObject({ tone: "warn", text: "Uvízlo: kritik hacker: Kritik: útok", detail: "čeká na tebe · únik tokenu", confirm: false });
    expect(cardState({ ...base, doneProposed: true, work: work({ waitingOnHuman: [{ blockId: "b", ask: "Smím smazat tabulku?" }] }) }))
      .toMatchObject({ tone: "warn", text: "Čeká na tebe", detail: "Smím smazat tabulku?" });
    expect(cardState({ ...base, doneProposed: true, work: work({ blockedBy: [{ id: "x", name: "3.2 Metadata" }] }) }))
      .toMatchObject({ tone: "warn", text: "Ke schválení", detail: "agent navrhl uzavření · blokuje: 3.2 Metadata", confirm: true });
    expect(cardState({ ...base, work: work({ status: "blocked", blockedBy: [{ id: "x", name: "3.2 Metadata" }] }) }))
      .toMatchObject({ tone: "fail", text: "Blokuje: 3.2 Metadata" });
  });

  it("names the working agent with its start, otherwise the stage on turn, the router or the frontier", () => {
    const claimed = cardState({ ...base, work: work({ status: "claimed", agent: "work-4.2-s1", startedAt: "2026-10-15T05:00:00Z" }) });
    expect(claimed).toMatchObject({ tone: "run", text: "Pracuje work-4.2-s1", since: "2026-10-15T05:00:00Z" });
    expect(cardState({ ...base, lease: { owner: "sonnet-1", expiresAt: 0, active: true, serverOffset: 0 } })).toMatchObject({ text: "Převzal sonnet-1", detail: "pronájem drží, činnost nehlášena" });
    const turn = process([dot("w", { status: "passed" }), dot("r", { kind: "review", current: true, title: "Code review" })]);
    expect(cardState({ ...base, process: turn })).toMatchObject({ tone: "idle", text: "Na řadě: review: Code review" });
    expect(cardState({ ...base, process: process([], { routed: false, proposed: 2 }) })).toMatchObject({ text: "Čeká na router", detail: "2 etap ke schválení" });
    expect(cardState({ ...base, frontier: { id: "n", name: "Karta", status: "frontier" } })).toMatchObject({ text: "K převzetí" });
    expect(cardState({ ...base, closed: true, doneProposed: true })).toMatchObject({ tone: "ok", text: "Uzavřeno" });
  });

  it("formats the working time in minutes and hours", () => {
    const now = Date.parse("2026-10-15T06:30:00Z");
    expect(sinceLabel("2026-10-15T06:18:00Z", now)).toBe("12 min");
    expect(sinceLabel("2026-10-15T04:05:00Z", now)).toBe("2 h 25 min");
    expect(sinceLabel(null, now)).toBe("");
    expect(sinceLabel("nesmysl", now)).toBe("");
  });
});
