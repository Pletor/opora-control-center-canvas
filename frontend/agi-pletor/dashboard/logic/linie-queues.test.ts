import { describe, expect, it } from "vitest";
import { boardFixture } from "./linie-fixture";
import { boardView } from "./linie-board";
import { NO_SOURCE, plural, queueLines, queues } from "./linie-queues";

const board = boardView(boardFixture);
const of = (...args: Parameters<typeof queues>) => Object.fromEntries(queues(...args).map((q) => [q.id, q]));

describe("fronty odpovědnosti", () => {
  it("počty z boardu s jednotkou, kuličky z ball.queues; kulička smí být ve dvou frontách", () => {
    const q = of(board.balls.map((b) => ({ ticketId: b.ticketId, queues: [...b.queues, ...(b.ticketId === "tk_4" ? ["gitQueue"] : [])] })), board.queues, 2);
    expect([q.clovek.count, q.tickety.count, q.kancelar.count, q.git.count, q.srdce.count, q.pletor.count]).toEqual(["1 rozhodnutí", "0 ticketů", "1 úkol", "1 PR", "2 plány", "2 otevřené žádosti"]);
    expect([q.clovek.ids, q.kancelar.ids, q.git.ids]).toEqual([["tk_4"], ["tk_2"], ["tk_1", "tk_4"]]);
    expect(queues([], board.queues, 2).every((q) => q.source)).toBe(true);
  });
  it("zdroj, který board nenese, počet nevymýšlí", () => {
    const q = of([], { ...board.queues!, plansWaiting: null }, null);
    expect([q.srdce.count, q.srdce.source, q.pletor.count, q.pletor.source, q.clovek.source]).toEqual([NO_SOURCE, false, NO_SOURCE, false, true]);
    expect(of([], null, null).git).toMatchObject({ count: NO_SOURCE, source: false });
    expect([plural(1, "úkol", "úkoly", "úkolů"), plural(3, "úkol", "úkoly", "úkolů"), plural(5, "úkol", "úkoly", "úkolů")]).toEqual(["1 úkol", "3 úkoly", "5 úkolů"]);
  });
  it("výrok bez výběru jmenuje jen fronty se zdrojem", () => {
    expect(queueLines(queues([], { ...board.queues!, plansWaiting: null }, null), 4)).toEqual(["Na plátně 4 kuličky.", "Člověk: 1 rozhodnutí.", "Tickety: 0 ticketů.", "Kancelář: 1 úkol.", "Git: 1 PR.",
      "Klikni na kuličku nebo frontu; řeknu, co o ní vím, odkud a co je další krok."]);
  });
});
