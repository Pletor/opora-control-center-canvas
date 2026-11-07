import { describe, expect, it } from "vitest";
import { boardView, layoutBoard } from "./linie-board";
import { chainOf, followsOf, foldClosed, forcedOpen, knotTip, placeKnots, reopenOf, toggleKnot, UNFOLD_KEY } from "./linie-closed";
import { readFolded } from "./linie-fold";
import { xOf } from "./linie-zoom";

const row = (id: string, branch: string, parent: string, extra: object = {}) => ({ id, name: branch, type: "work", branch, parent, auto: true, ...extra });
const shut = (at: string, balls: number, target: string) => ({ closed: { at, sha: "0000ac58aa", target, by: "merge", balls } });
const raw = {
  rows: [
    row("develop", "develop", "", { type: "develop" }), row("velin", "feat/velin", "develop"),
    row("linie", "feat/velin-linie", "feat/velin", shut("2026-11-07T15:15:00Z", 2, "feat/velin")),
    row("strom", "feat/velin-linie-strom", "feat/velin-linie", shut("2026-11-07T14:00:00Z", 1, "feat/velin-linie")),
  ],
  balls: [
    { ticketId: "v", rowId: "velin", title: "V", createdAt: "2026-11-07T10:00:00Z" },
    { ticketId: "l1", rowId: "linie", title: "L1", state: "merged", createdAt: "2026-11-07T11:00:00Z", mergedAt: "2026-11-07T15:15:00Z", links: [{ to: "v", kind: "merged" }] },
    { ticketId: "l2", rowId: "linie", title: "L2", state: "merged", createdAt: "2026-11-07T12:00:00Z" },
    { ticketId: "s", rowId: "strom", title: "S", state: "merged", createdAt: "2026-11-07T13:00:00Z" },
  ],
};
const board = boardView(raw);
const ids = (rows: { id: string }[]) => rows.map((r) => r.id);

describe("skládání uzavřených větví do rodiče", () => {
  it("uzavřený řádek s podstromem se nekreslí, rodič má značku v x(closed.at) se součtem kaskády", () => {
    const folded = foldClosed(board, new Set(), false);
    expect(ids(folded.board.rows)).toEqual(["develop", "velin"]);
    expect(folded.board.balls).toHaveLength(4); // kuličky zůstávají, rozsah času se při skládání nehne
    const layout = layoutBoard(folded.board);
    expect(layout.balls.map((b) => b.ticketId)).toEqual(["v"]);
    expect(layout.links).toEqual([]); // merge oblouk složené větve se nekreslí
    const [knot] = placeKnots(folded.knots, layout);
    expect(placeKnots(folded.knots, layout)).toHaveLength(1);
    expect(knot).toMatchObject({ rowId: "linie", parentId: "velin", open: false, label: "feat/velin-linie · 1 větev · 3 kuličky", sha7: "0000ac5" });
    expect(knot.x).toBeCloseTo(xOf({ t0: layout.t0, k: layout.k }, Date.parse("2026-11-07T15:15:00Z")));
    expect(knot.y).toBe(layout.rows.find((r) => r.id === "velin")!.y);
    expect(knotTip(knot)).toMatchObject({ title: knot.label, hint: "klik = rozbalit", rows: [{ k: "uzavřeno" }, { k: "merge", v: "0000ac5" }] });
  });

  it("tag na commitu kuličky složené větve se nekreslí (ani náhradou na main)", () => {
    const tagged = boardView({ ...raw, tags: [{ name: "v1", sha: "c1", at: "2026-11-07T12:30:00Z" }],
      balls: raw.balls.map((b) => (b.ticketId === "l2" ? { ...b, commits: [{ sha: "c1", title: "x", at: "2026-11-07T12:30:00Z" }] } : b)) });
    expect(layoutBoard(foldClosed(tagged, new Set(), false).board).tags).toEqual([]);
    expect(layoutBoard(foldClosed(tagged, new Set(), true).board).tags.map((t) => t.text)).toEqual(["v1"]);
  });

  it("klik přepne unfolded; každá úroveň kaskády se rozbaluje zvlášť", () => {
    const once = toggleKnot(new Set(), { rowId: "linie", open: false });
    expect([...once]).toEqual(["linie"]);
    const open = foldClosed(board, once, false);
    expect(ids(open.board.rows)).toEqual(["develop", "velin", "linie"]);
    expect(open.knots.map((k) => [k.rowId, k.parentId, k.open, k.label])).toEqual([
      ["linie", "velin", true, "feat/velin-linie · 1 větev · 3 kuličky"], ["strom", "linie", false, "feat/velin-linie-strom · 1 kulička"]]);
    expect(knotTip(placeKnots(open.knots, layoutBoard(open.board))[0]).hint).toBe("klik = složit");
    expect([...toggleKnot(once, { rowId: "linie", open: true })]).toEqual([]);
  });

  it("výběr kuličky uvnitř složené větve otevře každou úroveň nad ní", () => {
    expect(chainOf(board.rows, "strom")).toEqual(["strom", "linie"]);
    expect(forcedOpen(board, "s", "")).toEqual(["strom", "linie"]);
    expect(forcedOpen(board, "", "feat/velin-linie")).toEqual(["linie"]);
    expect(ids(foldClosed(board, new Set(forcedOpen(board, "s", "")), false).board.rows)).toEqual(["develop", "velin", "linie", "strom"]);
  });

  it("vrstva Sloučené větve otevře vše a značky zůstanou jako ukazatele", () => {
    const all = foldClosed(board, new Set(), true);
    expect(ids(all.board.rows)).toEqual(ids(board.rows));
    expect(all.knots.map((k) => k.open)).toEqual([true, true]);
  });

  it("nová kulička vrátí closed: null a řádek se objeví pod rodičem", () => {
    const reopened = boardView({ ...raw, rows: raw.rows.map((r) => (r.id === "linie" ? { ...r, closed: null } : r)) });
    const shown = foldClosed(reopened, new Set(), false);
    expect(ids(shown.board.rows)).toEqual(["develop", "velin", "linie"]);
    expect(shown.knots.map((k) => k.rowId)).toEqual(["strom"]);
  });

  it("bez času uzavření leží značka na konci osy s „uzavřeno ?“", () => {
    const blind = boardView({ ...raw, rows: raw.rows.map((r) => (r.id === "linie" ? { ...r, closed: { ...shut("", 2, "feat/velin").closed, at: null, sha: null } } : r)) });
    const folded = foldClosed(blind, new Set(), false);
    const layout = layoutBoard(folded.board);
    const [knot] = placeKnots(folded.knots, layout);
    expect(knot.label).toBe("feat/velin-linie · 1 větev · 3 kuličky · uzavřeno ?");
    expect(knot.x).toBeCloseTo(xOf({ t0: layout.t0, k: layout.k }, layout.t1));
  });

  it("formulář pozná uzavřenou větev; detail navazuje na začleněné kuličky téže větve", () => {
    expect(reopenOf(board.rows, " feat/velin-linie ")?.closed?.target).toBe("feat/velin");
    expect(reopenOf(board.rows, "feat/velin")).toBeUndefined();
    expect(reopenOf(board.rows, "")).toBeUndefined();
    const fresh = boardView({ ...raw, balls: [...raw.balls, { ticketId: "n", rowId: "linie", title: "N", state: "open" }] });
    expect(followsOf(fresh.balls, fresh.balls.find((b) => b.ticketId === "n"))).toBe(2);
    expect(followsOf(fresh.balls, fresh.balls.find((b) => b.ticketId === "l1"))).toBe(0);
  });

  it("rozbalení je uložené pro aplikaci pod vlastním klíčem", () => {
    expect([...readFolded({ getItem: (key) => (key === UNFOLD_KEY ? '["linie"]' : null) }, UNFOLD_KEY)]).toEqual(["linie"]);
  });
});
