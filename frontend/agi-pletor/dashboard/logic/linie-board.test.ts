import { describe, expect, it } from "vitest";
import { boardFixture } from "./linie-fixture";
import { LANE, PAD, PR_AT, ROW_FOLDED, ROW_OPEN, ROW_THIN, SPAN, boardView, layoutBoard, prPill, timeRange } from "./linie-board";
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
    expect(boardView(null)).toEqual({ rows: [], balls: [], mapping: { main: "main", develop: "develop" }, realMerges: [], snapshot: null, group: "branch", tags: [], worktrees: [], deploy: [], queues: null });
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
  it("x podle času, y podle řádku, glyf podle souhrnu; sbalený řádek kuličky skryje", () => {
    // osa začíná první kuličkou (4. 11. 10:00) a končí posledním časem (6. 11. 10:00)
    expect(ball("tk_3").x).toBe(PAD);
    expect(ball("tk_1").x).toBeCloseTo(PAD + (24 / 48) * SPAN);
    expect(ball("tk_1").y).toBe(2 * ROW_THIN + ROW_OPEN + ROW_OPEN / 2);
    expect(ball("tk_2").x).toBeCloseTo(PAD + (24.5 / 48) * SPAN); // vlastní čas, žádný rozestup
    expect(ball("tk_1").stateLabel).toBe("přijato, čeká na začlenění 9c8050f · 2 c · 1 ✕"); // popisek nese souhrn a commity
    expect(ball("tk_2").stateLabel).toBe("otevřeno"); // bez summary náhradou stateLabel
    expect([ball("tk_1").glyph.core, ball("tk_2").glyph.core, ball("tk_3").glyph.core]).toEqual(["full", "open", "full"]);
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
    expect(ball("tk_1").hover).toMatchObject({ reason: "checks.passed(HEAD) & acceptance.accepted(HEAD) & integration.none", next: "Služba začlení do topic/knihovna (znovu ověří)." });
    expect(layout.merges).toEqual([]); // merge 3. 11. je starší než první kulička, osa ho nekreslí
    const inside = layoutBoard(boardView({ ...boardFixture, realMerges: [{ ...boardFixture.realMerges[0], at: "2026-11-05T10:00:00Z" }] }));
    expect(inside.merges).toEqual([{ x: PAD + SPAN / 2, y: ROW_THIN / 2, sha7: "abcdef0", title: "develop → main", color: "#4ade80" }]);
    expect(layout.ticks.length).toBeGreaterThan(3);
    expect(layout.ticks[1].x - layout.ticks[0].x).toBeGreaterThanOrEqual(84);
    expect(layout.width).toBeGreaterThanOrEqual(PAD + SPAN + PAD);
  });
  it("kuličky se stejným časem leží na stejném x: čas se nikdy neposouvá, uhýbají jen popisky", () => {
    const at = "2026-11-01T10:00:00Z";
    const ball3 = ["a", "b", "c"].map((id) => ({ ticketId: id, rowId: "row_k", title: id, createdAt: at }));
    const xs = layoutBoard(boardView({ ...boardFixture, balls: ball3, realMerges: [] })).balls.map((b) => b.x);
    expect(new Set(xs).size).toBe(1);
  });
  it("commity z boardu (náhradou z evidence) leží na řádku své kuličky v čase commitu, opuštěný nese ✕; now rozšíří osu", () => {
    expect(layout.commits.map((c) => [c.ticketId, c.ref, c.y, c.abandoned])).toEqual([["tk_1", "1f0c2aa", ball("tk_1").y, false], ["tk_1", "deadbee", ball("tk_1").y, true], ["tk_1", "9c8050f", ball("tk_1").y, false]]);
    const fromEvidence = layoutBoard(boardView({ ...boardFixture, balls: [{ ...boardFixture.balls[0], commits: undefined }] }));
    expect(fromEvidence.commits.map((c) => c.ref)).toEqual(["1f0c2aa", "9c8050f"]);
    // čára práce: od kuličky k poslednímu živému commitu; odevzdaná práce plně
    expect(layout.works).toEqual([{ ticketId: "tk_1", x1: ball("tk_1").x, x2: layout.commits[2].x, y: ball("tk_1").y, color: ball("tk_1").color, wip: false }]);
    const now = Date.parse("2026-11-07T10:00:00Z");
    expect(timeRange(board, now).t1).toBe(now);
    expect(layoutBoard(board, { now }).now).toBe(now);
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
    expect(ball("tk_1").x).toBeCloseTo(PAD + (24 / 48) * SPAN);
    expect(layoutBoard(board, { k: 2000 / (48 * 3600e3) }).balls.find((b) => b.ticketId === "tk_1")!.x).toBeCloseTo(PAD + (24 / 48) * 2000);
  });
});

describe("skutečná data L7c a pohled podle plánu L7d", () => {
  it("PR z `pr` velkými písmeny; openPr jen z OPEN; po výpadku pilulka „neověřeno“ na 65 % merge oblouku", () => {
    expect(board.balls[0].pr).toEqual({ number: "7", state: "OPEN", url: "https://x/pr/7", unconfirmed: true });
    expect([board.balls[0].openPr, board.balls[2].openPr, board.balls[1].pr]).toEqual([true, false, null]);
    expect(prPill(board.balls[0])).toEqual({ text: "PR #7 · neověřeno", state: "open", unverified: true, url: "https://x/pr/7" });
    expect(prPill(boardView({ balls: [{ ticketId: "x", pr: { number: 9, state: "merged" } }] }).balls[0])).toMatchObject({ text: "PR #9 · sloučen", unverified: false });
    const planned = layout.links.find((l) => l.ticketId === "tk_1" && l.kind === "planned")!;
    expect(planned.pr!.at).toEqual({ x: (planned.from.x + planned.to.x) / 2, y: (planned.from.y + planned.to.y) / 2 });
    const merged = layout.links.find((l) => l.kind === "merged")!;
    expect(merged.pr!.at.x).toBeCloseTo(merged.from.x + (merged.to.x - merged.from.x) * PR_AT);
    expect(layout.links.find((l) => l.kind === "follows")!.pr).toBeNull();
  });
  it("tag leží na řádku kuličky s commitem, nasazení s původem na řádku cíle; worktree pruh jen s vazbou a jen pro zvolené řádky", () => {
    expect(layout.tags).toEqual([
      { x: layout.commits[0].x + (layout.commits[1].x - layout.commits[0].x) / 4, y: ball("tk_1").y, text: "v0.9.3", kind: "tag", title: "tag v0.9.3 na 1f0c2aa · git" },
      { x: expect.any(Number), y: ROW_THIN / 2, text: "staging@abcdef0", kind: "deploy", title: "nasazení potvrzené prostředím" },
    ]);
    expect(layout.lanes).toEqual([]);
    expect(layout.rows[3].height).toBe(ROW_OPEN);
    const withLanes = layoutBoard(board, { lanes: new Set(["row_k"]) });
    expect(withLanes.rows[3]).toMatchObject({ lanes: 1, height: ROW_OPEN + LANE, y: 2 * ROW_THIN + ROW_OPEN + ROW_OPEN / 2 });
    expect(withLanes.lanes).toEqual([{ rowId: "row_k", ticketId: "tk_1", agent: "agent-a", state: "pracuje", x1: expect.any(Number), x2: withLanes.width - PAD, y: withLanes.rows[3].top + ROW_OPEN + LANE / 2, color: ball("tk_1").color }]);
    expect(withLanes.height).toBe(layout.height + LANE);
  });
  it("fronty boardu a fronty kuličky; vazba na plán s rozdílem revize", () => {
    expect(board.queues).toEqual({ plansWaiting: 2, ticketsTodo: 0, humanDecisions: 1, officeTasks: 1, gitQueue: 1 });
    expect(boardView({ queues: { plansWaiting: null, gitQueue: 1 } }).queues).toEqual({ plansWaiting: null, ticketsTodo: null, humanDecisions: null, officeTasks: null, gitQueue: 1 });
    expect(board.balls[0].queues).toEqual(["gitQueue"]);
    expect(board.balls[0].judgement.plan).toEqual({ state: "linked", text: "plán card_p1 R3", diff: true, planCardId: "card_p1", directionCardId: "card_d1", cardRevision: "3", issued: { cardId: "card_p1", cardRevision: "2", at: "2026-11-05T10:00:00Z" } });
    expect(board.balls[1].judgement.plan).toBeNull();
  });
  it("řádky podle plánu: směr pevný, plán pod ním podle id rodiče, bez větve", () => {
    const grouped = boardView({ group: "plan", rows: [{ id: "dir:d1", type: "dir", name: "Velín", cardId: "d1", parent: null, depth: 0 }, { id: "plan:p1", type: "plan", name: "Linie", cardId: "p1", parent: "dir:d1", depth: 1 }, { id: "plan:none", type: "plan", name: "bez plánu", parent: null, depth: 0 }],
      balls: [{ ticketId: "a", rowId: "plan:p1", title: "A" }] });
    expect(grouped.group).toBe("plan");
    expect(grouped.rows.map((r) => [r.type, r.fixed, r.parent, r.cardId])).toEqual([["dir", true, "", "d1"], ["plan", false, "dir:d1", "p1"], ["plan", false, "", ""]]);
    expect(layoutBoard(grouped).rows.map((r) => [r.branchText, r.mappingText, r.height])).toEqual([["plátno 2 · směr", "", ROW_THIN], ["plátno 3 · plán", "", ROW_OPEN], ["plátno 3 · plán", "", ROW_THIN]]);
  });
});
