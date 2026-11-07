import { describe, expect, it } from "vitest";
import { boardFixture } from "./linie-fixture";
import { L2, LANE, PAD, PR_AT, ROW_FOLDED, ROW_OPEN, ROW_THIN, SPAN, boardView, layoutBoard, prPill, timeRange } from "./linie-board";
import { hueOf } from "./linie-color";
import { labelOffsets } from "./linie-labels";

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
    expect([ROW_THIN, ROW_OPEN, ROW_FOLDED, L2, LANE]).toEqual([36, 78, 46, 28, 20]); // hodnoty z prototypu Linie v3
    expect(layout.rows.map((row) => row.y - row.top)).toEqual([18, 18, 39, 39, 23]); // osa = base/2
    expect(layout.rows.map((row) => row.ind)).toEqual([8, 8, 40, 8, 8]); // 8 + 16·min(hloubka, 5)
    expect(layout.height).toBe(2 * ROW_THIN + 2 * ROW_OPEN + ROW_FOLDED);
  });
  it("barvy podle větve, popis větve a mapování", () => {
    // items fialová; řádek práce bez větve a rodiče je kořenem s vlastním odstínem ze jména
    expect(layout.rows.map((row) => row.color)).toEqual(["#4ade80", "#60a5fa", "#c084fc", `hsl(${hueOf("Komponenty")} 75% 56%)`, "#f87171"]);
    expect(layoutBoard(boardView({ rows: [{ id: "items", type: "items", fixed: true }] })).rows[0].meta).toBe("větev items/<díl> · cíl: develop nebo feat, kde je díl potřeba");
    expect(layout.rows[0].meta).toBe("větev main · mapování: Main → main");
    expect(layout.rows[3].meta).toBe("větev — · z topic/knihovna → cíl topic/knihovna");
    expect(layout.rows[2].meta).toBe("větev topic/knihovna · cíl: develop nebo feat, kde je díl potřeba");
    expect(layoutBoard(boardView({ rows: [{ id: "x", type: "experiment", branch: "experiment/webgl", parent: "feat/a" }] })).rows[0].meta).toBe("větev experiment/webgl · fork z feat/a · zpět nebo zahodit");
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
    const komponenty = `hsl(${hueOf("Komponenty")} 75% 56%)`;
    expect(layout.links.map((link) => [link.fromColor, link.toColor])).toEqual([
      [komponenty, komponenty], [komponenty, "#c084fc"], [komponenty, "#c084fc"], ["#c084fc", "#60a5fa"]]);
    expect([ball("tk_1").toColor, ball("tk_2").toColor, ball("tk_3").toColor]).toEqual(["#c084fc", "#c084fc", "#60a5fa"]);
    expect(layoutBoard(boardView({ rows: [{ id: "r", name: "R" }], balls: [{ ticketId: "x", rowId: "r" }] })).balls[0].toColor).toBe(`hsl(${hueOf("R")} 75% 56%)`);
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
    expect(layoutBoard(withGit).rows[5].meta).toBe("větev feat/x · 4 před develop · bez úkolu");
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
    // s pruhem jen popisky nad osou: tk_2 leží 8 px od tk_1, takže jde do druhého patra nad osou (+L2 jen jednou)
    const withLanes = layoutBoard(board, { lanes: new Set(["row_k"]) });
    const base = ROW_OPEN + L2;
    expect(withLanes.rows[3]).toMatchObject({ lanes: 1, height: base + LANE, y: 2 * ROW_THIN + ROW_OPEN + base - ROW_OPEN / 2 });
    expect(withLanes.labels.slots).toMatchObject({ tk_1: { side: -1, tier: 1 }, tk_2: { side: -1, tier: 2 } });
    expect(withLanes.lanes).toEqual([{ rowId: "row_k", ticketId: "tk_1", agent: "agent-a", state: "pracuje", x1: expect.any(Number), x2: withLanes.width - PAD, y: withLanes.rows[3].top + base + LANE / 2,
      color: ball("tk_1").color, dIn: expect.any(String), dOut: null, back: null }]);
    expect(withLanes.height).toBe(layout.height + L2 + LANE);
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
    expect(layoutBoard(grouped).rows.map((r) => [r.meta, r.height])).toEqual([["plátno 2 · směr", ROW_THIN], ["plátno 3 · plán", ROW_OPEN], ["plátno 3 · plán", ROW_THIN]]);
  });
});

describe("kresba větve podle prototypu (L9a)", () => {
  const rows = [
    { id: "dev", name: "Develop", type: "develop", branch: "develop", fixed: true },
    { id: "a", name: "A", type: "work", branch: "feat/a", parent: "develop", depth: 2 },
    { id: "ab", name: "AB", type: "work", branch: "feat/a-b", parent: "feat/a", depth: 3 },
  ];
  const at = (h: number) => `2026-11-07T${String(h).padStart(2, "0")}:00:00Z`;
  const wt = (ticketId: string, from: string, to: string | null) => ({ path: `C:/wt/${ticketId}${from}`, branch: "feat/a-b", sha: "s", binding: { ticketId, agent: "agent A", from, to, live: !to } });
  const twoLanes = boardView({ rows, balls: [{ ticketId: "x", rowId: "ab", title: "X", createdAt: at(8) }, { ticketId: "y", rowId: "dev", title: "Y", createdAt: at(12) }],
    worktrees: [wt("x", at(9), at(10)), wt("x", at(10), null)] });

  it("řádek se dvěma pruhy roste dolů, osa zůstane v base/2; pruh s návratem a tečkou „vrácen“, bez návratu jen odbočka", () => {
    const laid = layoutBoard(twoLanes, { lanes: new Set(["ab"]) });
    const row = laid.rows[2];
    expect([row.height, row.y - row.top, row.lanes]).toEqual([ROW_OPEN + 2 * LANE, ROW_OPEN / 2, 2]);
    const x9 = laid.balls[0].x + (laid.balls[1].x - laid.balls[0].x) / 4, x10 = laid.balls[0].x + (laid.balls[1].x - laid.balls[0].x) / 2;
    const [back, open] = laid.lanes;
    expect(back).toMatchObject({ state: "vrácen", x1: x9 + 14, x2: x10, y: row.top + ROW_OPEN + 10, dIn: `M${x9} ${row.y} L${x9 + 14} ${row.top + ROW_OPEN + 10}`,
      dOut: `M${x10} ${row.top + ROW_OPEN + 10} L${x10 + 14} ${row.y}`, back: { x: x10 + 14, y: row.y } });
    expect(open).toMatchObject({ state: "pracuje", x1: x10 + 14, y: row.top + ROW_OPEN + 30, dOut: null, back: null });
  });
  it("druhé patro bez pruhů zvedne řádek o 2·L2 (nad i pod osou), osa je dál uprostřed", () => {
    const crowded = boardView({ rows, balls: ["p", "q", "r"].map((id, i) => ({ ticketId: id, rowId: "a", title: id, createdAt: at(8 + i) })).concat({ ticketId: "z", rowId: "a", title: "z", createdAt: at(20) }) });
    const laid = layoutBoard(crowded);
    expect(laid.labels.slots.r).toEqual({ side: 1, tier: 2 });
    expect([laid.rows[1].height, laid.rows[1].y - laid.rows[1].top]).toEqual([ROW_OPEN + 2 * L2, (ROW_OPEN + 2 * L2) / 2]);
  });
  it("popisky ve všech patrech zůstanou uvnitř svého řádku (s pruhy i bez)", () => {
    const busy = (lanes: boolean) => layoutBoard(boardView({ rows, balls: ["p", "q", "r", "s"].map((id, i) => ({ ticketId: id, rowId: "ab", title: id, createdAt: at(8 + i) })).concat({ ticketId: "z", rowId: "ab", title: "z", createdAt: at(20) }),
      worktrees: [wt("p", at(9), null)] }), { lanes: new Set(lanes ? ["ab"] : []) });
    for (const laid of [busy(false), busy(true)]) {
      const row = laid.rows[2], base = row.height - LANE * row.lanes;
      expect(Object.values(laid.labels.slots).some((slot) => slot.tier === 2)).toBe(true);
      for (const slot of Object.values(laid.labels.slots)) {
        const off = labelOffsets(slot);
        expect(row.y + off.name - 10).toBeGreaterThanOrEqual(row.top);
        expect(row.y + off.state + 3).toBeLessThanOrEqual(row.top + base);
      }
    }
  });
  it("barva potomka z kořenové větve: stejný odstín, světlejší podle úrovně", () => {
    const laid = layoutBoard(twoLanes);
    expect(laid.rows.map((r) => r.color)).toEqual(["#60a5fa", `hsl(${hueOf("feat/a")} 75% 56%)`, `hsl(${hueOf("feat/a")} 66% 64%)`]);
  });
  it("merge končí na ose cíle v čase merge, ne u kuličky; pilulka u cíle s · squash", () => {
    const merged = boardView({ rows, balls: [{ ticketId: "m", rowId: "ab", title: "M", createdAt: at(8), mergedAt: at(12), links: [{ to: "a", kind: "merged" }], pr: { number: 3, state: "MERGED" },
      axes: { integration: { state: "merged", target: "feat/a", mode: "squash", at: at(12) } }, summary: { key: "merged", text: "začleněno" },
      commits: [{ sha: "c1full", sha7: "c1", title: "c", at: at(9) }] }] });
    const laid = layoutBoard(merged, { now: Date.parse(at(16)) });
    const link = laid.links[0];
    expect(link.to).toEqual({ x: PAD + (4 / 8) * SPAN, y: laid.rows[1].y });
    expect(link.pr!.text).toBe("PR #3 · sloučen · squash");
    // začleněná kulička: kostka i čára práce v barvě cíle
    expect([laid.commits[0].color, laid.works[0].color, laid.commits[0].sha]).toEqual([laid.rows[1].color, laid.rows[1].color, "c1full"]);
  });
  it("plán vychází z posledního živého commitu a míří 110 px doprava na osu cíle; popisek plán → cíl", () => {
    const planned = boardView({ rows, balls: [{ ticketId: "p", rowId: "ab", title: "P", createdAt: at(8), links: [{ to: "a", kind: "planned" }], summary: { key: "blocked" },
      commits: [{ sha: "c1", sha7: "c1", title: "c", at: at(10) }, { sha: "c2", sha7: "c2", title: "d", at: at(11), abandoned: { why: "x" } }] }], worktrees: [] });
    const laid = layoutBoard(planned, { now: Date.parse(at(12)) });
    const link = laid.links[0], commitX = laid.commits[0].x;
    expect([link.from, link.to, link.openEnd]).toEqual([{ x: commitX, y: laid.rows[2].y }, { x: commitX + 110, y: laid.rows[1].y }, true]);
    expect(link.label).toBe("blokováno · plán → a");
  });
});
