import { describe, expect, it } from "vitest";
import { boardView, layoutBoard, ROW_FOLDED, ROW_OPEN, ROW_THIN } from "./linie-board";
import { descendants, focusRows, foldChip, readFolded, shownBoard, visibleRows } from "./linie-fold";

const row = (id: string, branch: string, parent: string, extra: object = {}) => ({ id, name: branch || id, type: "work", branch, parent, auto: true, ...extra });
const board = boardView({
  rows: [
    row("main", "main", "", { type: "main" }), row("develop", "develop", "main", { type: "develop" }),
    row("items", "", "", { type: "items", fixed: true, auto: false }), row("btn", "items/btn", "develop", { type: "items" }),
    row("velin", "feat/velin", "develop"), row("linie", "feat/velin-linie", "feat/velin"),
    row("strom", "feat/velin-linie-strom", "feat/velin-linie"), row("barvy", "feat/velin-linie-barvy", "feat/velin-linie"),
    row("vodotisk", "feat/velin-vodotisk", "feat/velin"), row("canvas", "feat/canvas-2", "develop"),
  ],
  balls: [
    { ticketId: "t1", rowId: "strom", title: "L5" }, { ticketId: "t2", rowId: "barvy", title: "L6", links: [{ to: "linie", kind: "planned" }] },
    { ticketId: "t3", rowId: "velin", title: "V" }, { ticketId: "t4", rowId: "canvas", title: "C" },
  ],
});
const ids = (rows: { id: string }[]) => rows.map((r) => r.id);
const at = (id: string) => board.rows.find((r) => r.id === id)!;

describe("descendants a visibleRows", () => {
  it("potomci po řetězu parent; hlavička Items drží items/*", () => {
    expect(ids(descendants(at("velin"), board.rows))).toEqual(["linie", "strom", "barvy", "vodotisk"]);
    expect(ids(descendants(at("items"), board.rows))).toEqual(["btn"]);
    expect(descendants(at("main"), board.rows)).toHaveLength(9);
  });
  it("sbalení Velínu schová čtyři řádky a řádek nese collapsed", () => {
    const shown = visibleRows(board.rows, new Set(["velin"]));
    expect(ids(shown)).toEqual(["main", "develop", "items", "btn", "velin", "canvas"]);
    expect(shown.find((r) => r.id === "velin")!.collapsed).toBe(true);
    expect(foldChip(at("velin"), board.rows, board.balls)).toBe("4 větví · 3 kuliček");
  });
  it("ruční collapsed ze serveru skryje potomky stejně", () => {
    const rows = board.rows.map((r) => (r.id === "linie" ? { ...r, collapsed: true } : r));
    expect(ids(visibleRows(rows, new Set()))).not.toContain("strom");
  });
});

describe("focusRows a shownBoard", () => {
  it("zaměření ukáže cestu ke kořeni a podstrom", () => {
    expect(focusRows(board.rows, "feat/velin-linie")).toEqual({ rows: ["main", "develop", "velin", "linie", "strom", "barvy"].map(at), path: ["velin", "develop", "main"] });
    expect(focusRows(board.rows, "feat/nikde").rows).toHaveLength(10);
  });
  it("řádky cesty jsou tenké bez kuliček, podstrom v plné výšce, sbalený nižší", () => {
    const { board: shown, chips } = shownBoard(board, new Set(["barvy"]), "feat/velin-linie");
    const laid = layoutBoard(shown);
    expect(laid.rows.map((r) => [r.id, r.height])).toEqual([
      ["main", ROW_THIN], ["develop", ROW_THIN], ["velin", ROW_THIN], ["linie", ROW_THIN], ["strom", ROW_OPEN], ["barvy", ROW_FOLDED]]);
    expect(laid.balls.map((b) => b.ticketId)).toEqual(["t1"]);
    expect(chips).toEqual({ barvy: "0 větví · 1 kuliček" });
  });
  it("puntík kuličky má barvu řádku cíle a dva kořeny mají různý odstín", () => {
    const laid = layoutBoard(board);
    const color = (id: string) => laid.rows.find((r) => r.id === id)!.color;
    expect(laid.balls.find((b) => b.ticketId === "t2")!.toColor).toBe(color("linie"));
    expect(color("velin")).not.toBe(color("canvas"));
    expect(color("linie")).toMatch(new RegExp(`^hsl\\(${color("velin").slice(4).split(" ")[0]} `));
  });
});

describe("pohled podle plánu", () => {
  it("sbalení směru schová plány pod ním (rodič je id řádku, ne větev)", () => {
    const plan = boardView({ rows: [{ id: "dir:d1", type: "dir", name: "Velín" }, { id: "plan:p1", type: "plan", name: "Linie", parent: "dir:d1" }, { id: "plan:none", type: "plan", name: "bez plánu" }] });
    expect(ids(descendants(plan.rows[0], plan.rows))).toEqual(["plan:p1"]);
    expect(ids(visibleRows(plan.rows, new Set(["dir:d1"])))).toEqual(["dir:d1", "plan:none"]);
  });
});

describe("readFolded", () => {
  it("čte pole id, chybná hodnota je prázdná množina", () => {
    expect([...readFolded({ getItem: () => '["velin", 3]' })]).toEqual(["velin"]);
    expect(readFolded({ getItem: () => "{" }).size).toBe(0);
    expect(readFolded(undefined).size).toBe(0);
  });
});
