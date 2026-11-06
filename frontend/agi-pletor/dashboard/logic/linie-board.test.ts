import { describe, expect, it } from "vitest";
import { boardFixture } from "./linie-fixture";
import { MIN_GAP, PAD, ROW_FOLDED, ROW_OPEN, ROW_THIN, SPAN, boardView, layoutBoard, legend, pletorSentence } from "./linie-board";
import { hueOf } from "./linie-color";

const board = boardView(boardFixture);
const layout = layoutBoard(board);
const ball = (id: string) => layout.balls.find((item) => item.ticketId === id)!;

describe("boardView", () => {
  it("mapuje řádky, kuličky a spojnice; pevné Main a Develop", () => {
    expect(board.rows.map((row) => [row.id, row.type, row.fixed])).toEqual([
      ["main", "main", true], ["develop", "develop", true], ["row_t", "items", false], ["row_k", "work", false], ["row_f", "fix", false]]);
    expect(board.rows[3].branch).toBe("");
    expect(board.balls[0].links).toEqual([{ to: "tk_2", kind: "follows" }, { to: "row_t", kind: "planned" }]);
  });
  it("parent a depth ze strom odpovědi, topic se čte jako items", () => {
    expect(board.rows[2]).toMatchObject({ type: "items", parent: "develop", depth: 2 });
    expect(board.rows[0]).toMatchObject({ parent: "", depth: 0 });
    expect(boardView({ rows: [{ id: "a", type: "topic" }] }).rows[0].type).toBe("items");
  });
  it("chybná odpověď nespadne a neznámý stav je otevřeno", () => {
    expect(boardView(null)).toEqual({ rows: [], balls: [], mapping: { main: "main", develop: "develop" }, realMerges: [] });
    expect(boardView({ balls: [{ ticketId: "x", state: "??" }] }).balls[0]).toMatchObject({ state: "open", stateLabel: "otevřeno" });
    expect(layoutBoard(boardView(null)).balls).toEqual([]);
  });
});

describe("layoutBoard", () => {
  it("řádky pod sebou: bez kuliček tenký, s kuličkami plný, sbalený pojme dva řádky textu", () => {
    expect(layout.rows.map((row) => row.height)).toEqual([ROW_THIN, ROW_THIN, ROW_OPEN, ROW_OPEN, ROW_FOLDED]);
    expect(layout.rows.map((row) => row.top)).toEqual([0, ROW_THIN, 2 * ROW_THIN, 2 * ROW_THIN + ROW_OPEN, 2 * ROW_THIN + 2 * ROW_OPEN]);
    expect(ROW_FOLDED).toBeGreaterThanOrEqual(2 * 18 + 12);
    expect(layout.height).toBe(2 * ROW_THIN + 2 * ROW_OPEN + ROW_FOLDED);
  });
  it("barvy podle větve, popis větve a mapování", () => {
    // items fialová; řádek práce bez větve a rodiče je kořenem s vlastním odstínem ze jména
    expect(layout.rows.map((row) => row.color)).toEqual(["#4ade80", "#60a5fa", "#c084fc", `hsl(${hueOf("Komponenty")} 72% 52%)`, "#f87171"]);
    expect(layoutBoard(boardView({ rows: [{ id: "items", type: "items", fixed: true }] })).rows[0]).toMatchObject({ branchText: "větve items/<díl>", mappingText: "cíl: develop nebo feat větev, kde je díl potřeba" });
    expect(layout.rows[0].mappingText).toBe("mapování: Main → main");
    expect(layout.rows[3].branchText).toBe("bez větve");
    expect(layout.rows[2].branchText).toBe("větev: topic/knihovna");
  });
  it("x podle času, y podle řádku, výplň podle stavu; sbalený řádek kuličky skryje", () => {
    expect(ball("tk_3").x).toBeCloseTo(PAD + (24 / 72) * SPAN);
    expect(ball("tk_1").y).toBe(2 * ROW_THIN + ROW_OPEN + ROW_OPEN / 2);
    expect(ball("tk_2").x - ball("tk_1").x).toBe(MIN_GAP);
    expect([ball("tk_1").fill, ball("tk_2").fill, ball("tk_3").fill]).toEqual(["done", "open", "merged"]);
    expect(layout.balls.some((item) => item.ticketId === "tk_4")).toBe(false);
  });
  it("plán je čárkovaný s otevřeným cílem, merge má bod, plán nikdy není merge", () => {
    expect(layout.links.map((link) => [link.kind, link.openEnd])).toEqual([["follows", false], ["planned", true], ["planned", true], ["merged", false]]);
    expect(layout.links[3].to).toEqual({ x: PAD + SPAN, y: ROW_THIN + ROW_THIN / 2 });
    expect(layout.links.filter((link) => link.kind === "merged")).toHaveLength(1);
  });
  it("spojnice vede gradientem od barvy zdroje k barvě cíle, puntík kuličky má barvu cíle", () => {
    const komponenty = `hsl(${hueOf("Komponenty")} 72% 52%)`;
    expect(layout.links.map((link) => [link.fromColor, link.toColor])).toEqual([
      [komponenty, komponenty], [komponenty, "#c084fc"], [komponenty, "#c084fc"], ["#c084fc", "#60a5fa"]]);
    expect([ball("tk_1").toColor, ball("tk_2").toColor, ball("tk_3").toColor]).toEqual(["#c084fc", "#c084fc", "#60a5fa"]);
    expect(layoutBoard(boardView({ rows: [{ id: "r", name: "R" }], balls: [{ ticketId: "x", rowId: "r" }] })).balls[0].toColor).toBe(`hsl(${hueOf("R")} 72% 52%)`);
  });
  it("hover nese název, stav, počty a větev; skutečné merge leží na řádku cíle", () => {
    expect(ball("tk_1").hover.mark).toBe("OP-3F9A1C");
    expect(ball("tk_2").hover.mark).toBe("");
    expect(ball("tk_1").hover).toMatchObject({ title: "Panel detailu karty", state: "hotovo, ještě nezačleněno", merged: "—", counts: "3 | 1 | 0", branch: "feat/detail-karty @ 9c8050f" });
    expect(layout.merges).toEqual([{ x: PAD, y: ROW_THIN / 2, sha7: "abcdef0", title: "develop → main", color: "#4ade80" }]);
    expect(layout.ticks).toHaveLength(3);
    expect(layout.width).toBeGreaterThanOrEqual(PAD + SPAN + PAD);
  });
  it("kuličky se stejným časem na jednom řádku se rozestoupí a nepřekryjí", () => {
    const at = "2026-11-01T10:00:00Z";
    const ball3 = ["a", "b", "c"].map((id) => ({ ticketId: id, rowId: "row_k", title: id, createdAt: at }));
    const xs = layoutBoard(boardView({ ...boardFixture, balls: ball3, realMerges: [] })).balls.map((b) => b.x);
    expect(new Set(xs).size).toBe(3);
    expect(xs[1] - xs[0]).toBeGreaterThanOrEqual(MIN_GAP);
    expect(xs[2] - xs[1]).toBeGreaterThanOrEqual(MIN_GAP);
  });
  it("auto a planned jsou bezpečně false", () => {
    expect(board.rows.every((row) => !row.auto && !row.planned)).toBe(true);
    expect(boardView({ rows: [{ id: "a", auto: true, planned: true }] }).rows[0]).toMatchObject({ auto: true, planned: true });
  });
  it("řádek z gitu (větev bez úkolu) je jen ke čtení a osa se roztáhne na zadanou šířku", () => {
    const withGit = boardView({ ...boardFixture, rows: [...boardFixture.rows, { id: "git:feat/x", name: "feat/x", type: "work", branch: "feat/x", base: { branch: "develop" }, target: "develop", git: true, ahead: 4 }] });
    const row = withGit.rows[5];
    expect([row.git, row.ahead, row.fixed]).toEqual([true, 4, false]);
    expect(layoutBoard(withGit).rows[5].branchText).toBe("větev: feat/x · 4 před develop · bez úkolu");
    expect(ball("tk_3").x).toBeCloseTo(PAD + (24 / 72) * SPAN);
    expect(layoutBoard(board, 2000).balls.find((b) => b.ticketId === "tk_3")!.x).toBeCloseTo(PAD + (24 / 72) * 2000);
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
