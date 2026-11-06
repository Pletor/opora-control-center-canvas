import { describe, expect, it } from "vitest";
import { boardFixture } from "./linie-fixture";
import { MIN_GAP, PAD, ROW_FOLDED, ROW_OPEN, SPAN, boardView, layoutBoard, legend, pletorSentence } from "./linie-board";

const board = boardView(boardFixture);
const layout = layoutBoard(board);
const ball = (id: string) => layout.balls.find((item) => item.ticketId === id)!;

describe("boardView", () => {
  it("mapuje řádky, kuličky a spojnice; pevné Main a Develop", () => {
    expect(board.rows.map((row) => [row.id, row.type, row.fixed])).toEqual([
      ["main", "main", true], ["develop", "develop", true], ["row_t", "topic", false], ["row_k", "work", false], ["row_f", "fix", false]]);
    expect(board.rows[3].branch).toBe("");
    expect(board.balls[0].links).toEqual([{ to: "tk_2", kind: "follows" }, { to: "row_t", kind: "planned" }]);
  });
  it("chybná odpověď nespadne a neznámý stav je otevřeno", () => {
    expect(boardView(null)).toEqual({ rows: [], balls: [], mapping: { main: "main", develop: "develop" }, realMerges: [] });
    expect(boardView({ balls: [{ ticketId: "x", state: "??" }] }).balls[0]).toMatchObject({ state: "open", stateLabel: "otevřeno" });
    expect(layoutBoard(boardView(null)).balls).toEqual([]);
  });
});

describe("layoutBoard", () => {
  it("řádky pod sebou, sbalený řádek je nižší, ale pojme dva řádky textu", () => {
    expect(layout.rows.map((row) => row.top)).toEqual([0, ROW_OPEN, 2 * ROW_OPEN, 3 * ROW_OPEN, 4 * ROW_OPEN]);
    expect(layout.rows[4].height).toBe(ROW_FOLDED);
    expect(ROW_FOLDED).toBeGreaterThanOrEqual(2 * 18 + 12);
    expect(layout.height).toBe(4 * ROW_OPEN + ROW_FOLDED);
  });
  it("barvy podle typu, popis větve a mapování", () => {
    expect(layout.rows.map((row) => row.color)).toEqual(["#4ade80", "#60a5fa", "#fb923c", "#c084fc", "#f87171"]);
    expect(layout.rows[0].mappingText).toBe("mapování: Main → main");
    expect(layout.rows[3].branchText).toBe("bez větve");
    expect(layout.rows[2].branchText).toBe("větev: topic/knihovna");
  });
  it("x podle času, y podle řádku, výplň podle stavu; sbalený řádek kuličky skryje", () => {
    expect(ball("tk_3").x).toBeCloseTo(PAD + (24 / 72) * SPAN);
    expect(ball("tk_1").y).toBe(3 * ROW_OPEN + ROW_OPEN / 2);
    expect(ball("tk_2").x - ball("tk_1").x).toBe(MIN_GAP);
    expect([ball("tk_1").fill, ball("tk_2").fill, ball("tk_3").fill]).toEqual(["done", "open", "merged"]);
    expect(layout.balls.some((item) => item.ticketId === "tk_4")).toBe(false);
  });
  it("plán je čárkovaný s otevřeným cílem, merge má bod, plán nikdy není merge", () => {
    expect(layout.links.map((link) => [link.kind, link.openEnd])).toEqual([["follows", false], ["planned", true], ["planned", true], ["merged", false]]);
    expect(layout.links[3].to).toEqual({ x: PAD + SPAN, y: ROW_OPEN + ROW_OPEN / 2 });
    expect(layout.links.filter((link) => link.kind === "merged")).toHaveLength(1);
  });
  it("hover nese název, stav, počty a větev; skutečné merge leží na řádku cíle", () => {
    expect(ball("tk_1").hover).toMatchObject({ title: "Panel detailu karty", state: "hotovo, ještě nezačleněno", merged: "—", counts: "3 | 1 | 0", branch: "feat/detail-karty @ 9c8050f" });
    expect(layout.merges).toEqual([{ x: PAD, y: ROW_OPEN / 2, sha7: "abcdef0", title: "develop → main", color: "#4ade80" }]);
    expect(layout.ticks).toHaveLength(3);
    expect(layout.width).toBeGreaterThanOrEqual(PAD + SPAN + PAD);
  });
});

describe("legenda a věta Pletora", () => {
  it("počty stavů i plánů, stavy textem", () => {
    const counts = Object.fromEntries(legend(board).map((item) => [item.text, item.count]));
    expect(counts).toMatchObject({ "začleněno": 1, "hotovo, ještě nezačleněno": 1, "otevřeno": 1, "blokováno": 1, "plán": 2 });
  });
  it("kde pracujeme, co je hotové a co blokované", () => {
    expect(pletorSentence(board)).toBe("Pracujeme na Datový uzel v řádku Komponenty; hotovo a čeká na začlenění: Panel detailu karty; blokováno: Oprava: ukládání popisu.");
    expect(pletorSentence(boardView({}))).toBe("Nic se právě nevyvíjí.");
  });
});
