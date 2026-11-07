import { describe, expect, it } from "vitest";
import { boardFixture } from "./linie-fixture";
import { boardView } from "./linie-board";
import { plural, queueLines, queues, type QueueBall } from "./linie-queues";

const of = (balls: QueueBall[]) => Object.fromEntries(queues(balls).map((q) => [q.id, q]));

describe("fronty odpovědnosti", () => {
  it("zařazení podle summary.key, kulička smí být ve dvou frontách", () => {
    const q = of([
      { ticketId: "a", key: "pending", openPr: true }, { ticketId: "b", key: "stale", openPr: false }, { ticketId: "c", key: "blocked", openPr: false },
      { ticketId: "d", key: "todo", openPr: false }, { ticketId: "e", key: "wip", openPr: false }, { ticketId: "f", key: "failed", openPr: false },
      { ticketId: "g", key: "nocheck", openPr: false }, { ticketId: "h", key: "checking", openPr: false }, { ticketId: "i", key: "accepted", openPr: false },
      { ticketId: "j", key: "merged", openPr: false },
    ]);
    expect(q.clovek.ids).toEqual(["a", "b", "c"]);
    expect(q.tickety.ids).toEqual(["d"]);
    expect(q.kancelar.ids).toEqual(["e", "f", "g"]);
    expect(q.git.ids).toEqual(["a", "h", "i"]); // „a“ čeká na člověka a zároveň má otevřený PR
  });
  it("každý počet s jednotkou; fronty bez zdroje nic nevymýšlejí", () => {
    const q = of([]);
    expect([q.clovek.count, q.tickety.count, q.kancelar.count, q.git.count]).toEqual(["0 rozhodnutí", "0 ticketů", "0 úkolů", "0 PR"]);
    expect([q.pletor.count, q.srdce.count, q.pletor.source]).toEqual(["— (zatím bez zdroje)", "— (zatím bez zdroje)", false]);
    expect([plural(1, "úkol", "úkoly", "úkolů"), plural(3, "úkol", "úkoly", "úkolů"), plural(5, "úkol", "úkoly", "úkolů")]).toEqual(["1 úkol", "3 úkoly", "5 úkolů"]);
    expect(plural(2, "ticket", "tickety", "ticketů")).toBe("2 tickety");
  });
  it("z fixture boardu: blokovaná u člověka, rozpracovaná v kanceláři, přijatá s PR v gitu", () => {
    const q = of(boardView(boardFixture).balls.map((b) => ({ ticketId: b.ticketId, key: b.judgement.summary.key, openPr: b.openPr })));
    expect([q.clovek.ids, q.kancelar.ids, q.git.ids, q.git.count, q.kancelar.count]).toEqual([["tk_4"], ["tk_2"], ["tk_1"], "1 PR", "1 úkol"]);
  });
  it("výrok bez výběru jmenuje jen fronty se zdrojem", () => {
    expect(queueLines(queues([]), 4)).toEqual(["Na plátně 4 kuličky.", "Člověk: 0 rozhodnutí.", "Tickety: 0 ticketů.", "Kancelář: 0 úkolů.", "Git: 0 PR.",
      "Klikni na kuličku nebo frontu; řeknu, co o ní vím, odkud a co je další krok."]);
  });
});
