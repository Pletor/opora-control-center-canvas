import { describe, expect, it } from "vitest";
import { boardView, layoutBoard } from "./linie-board";
import { boardFixture } from "./linie-fixture";
import { LEGEND, commitTail, glyphOf, legend } from "./linie-glyph";
import { KEYS, judgementOf, type SummaryKey } from "./linie-summary";

const ALL: SummaryKey[] = [...KEYS, "unknown"];
const ball = (key: SummaryKey) => ({ judgement: judgementOf({ summary: { key, text: key } }) });

describe("glyf ze summary.key (§2a, prototyp Linie v3)", () => {
  it("každý klíč tabulky §2a má glyf podle prototypu", () => {
    const shape = (key: SummaryKey) => { const g = glyphOf(key); return [g.core, g.halo, g.staleRing, g.blocked, g.aim]; };
    expect(Object.fromEntries(ALL.map((key) => [key, shape(key)]))).toEqual({
      todo: ["ghost", false, false, false, false],
      wip: ["open", false, false, false, true], failed: ["open", false, false, false, true],
      nocheck: ["open", false, false, false, true], checking: ["open", false, false, false, true],
      pending: ["full", true, false, false, true], accepted: ["full", true, false, false, true], stale: ["full", true, true, false, true],
      merged: ["full", false, false, false, false], blocked: ["plain", false, false, true, false],
      parked: ["parked", false, false, false, true], unknown: ["plain", false, false, false, true],
    });
  });
  it("nocheck po přijetí starší revize nese žlutý prstenec jako stale", () => {
    const j = judgementOf({ summary: { key: "nocheck" }, axes: { acceptance: { state: "accepted", sha: "a" } } });
    expect(glyphOf("nocheck", j).staleRing).toBe(true);
  });
  it("čekající na člověka se liší od rozpracované", () => {
    expect(glyphOf("pending")).not.toEqual({ ...glyphOf("wip"), key: "pending" });
  });
  it("žádný klíč bez glyfu ani mimo legendu; kuličky fixture mají glyf ze svého klíče", () => {
    expect(ALL.every((key) => LEGEND.filter((item) => item.keys.includes(key)).length === 1)).toBe(true);
    const laid = layoutBoard(boardView(boardFixture)).balls;
    expect(laid.length).toBeGreaterThan(0);
    for (const b of laid) expect(b.glyph).toEqual(glyphOf(b.key, boardView(boardFixture).balls.find((x) => x.ticketId === b.ticketId)!.judgement));
  });
});

describe("legenda počítá podle summary.key", () => {
  it("počty podle klíče, ne podle starého state; součet = počet kuliček", () => {
    const balls = [ball("pending"), ball("pending"), ball("stale"), ball("accepted"), ball("wip"), ball("todo"), ball("blocked"), ball("merged")];
    const items = legend(balls);
    const counts = Object.fromEntries(items.map((item) => [item.text, item.count]));
    expect(counts).toMatchObject({ "ticket bez pokusu": 1, "probíhá": 1, "odevzdáno, kontroly prošly": 3, "přijetí zastaralo": 1, "začleněno (barva cíle)": 1, "blokováno": 1 });
    expect(items.reduce((sum, item) => sum + item.count, 0)).toBe(balls.length);
    expect(counts["nevím"]).toBeUndefined(); // „nevím“ jen s takovou kuličkou
  });
  it("fixture: legenda sedí s klíči kuliček", () => {
    const board = boardView(boardFixture);
    const counts = Object.fromEntries(legend(board.balls).map((item) => [item.text, item.count]));
    expect(counts).toMatchObject({ "odevzdáno, kontroly prošly": 1, "probíhá": 1, "začleněno (barva cíle)": 1, "blokováno": 1 });
  });
});

describe("přípona popisku", () => {
  it("živé commity jako „c“, opuštěné jako „✕“, nuly se nepíšou", () => {
    expect(commitTail([{ abandoned: false }, { abandoned: true }, { abandoned: false }])).toBe(" · 2 c · 1 ✕");
    expect(commitTail([{ abandoned: true }])).toBe(" · 1 ✕");
    expect(commitTail([])).toBe("");
  });
});
