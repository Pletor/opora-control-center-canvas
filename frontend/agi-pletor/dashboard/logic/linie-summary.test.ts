import { describe, expect, it } from "vitest";
import { boardFixture } from "./linie-fixture";
import { boardView } from "./linie-board";
import { actionsOf, ago, hhmm, judgementOf, pletorVerdict, snapshotOf, sourceAges } from "./linie-summary";

const board = boardView(boardFixture);
const j = (id: string) => board.balls.find((b) => b.ticketId === id)!.judgement;
const now = Date.parse("2026-11-06T10:06:00Z");

describe("čtení summary a os", () => {
  it("summary z backendu platí, akce a důkazy se čtou", () => {
    expect(j("tk_1").summary).toEqual({ key: "accepted", text: "přijato, čeká na začlenění 9c8050f", reason: "checks.passed(HEAD) & acceptance.accepted(HEAD) & integration.none", next: "Služba začlení do topic/knihovna (znovu ověří).", derived: false });
    expect(j("tk_1").allowed).toEqual(["merge", "block"]);
    expect(j("tk_1").blocked).toEqual({ accept: "acceptance.accepted(HEAD) – už přijato" });
    expect(j("tk_1").incomplete).toEqual(["prs"]);
    expect(j("tk_1").axes?.checks).toEqual({ state: "passed", sha: "9c8050f1a2b3", src: "CI" });
    expect(board.balls[0].openPr).toBe(true);
  });
  it("bez summary: text ze stateLabel, další krok z next, klíč z dnešního state; bez allowed žádné akce", () => {
    expect(j("tk_2").summary).toEqual({ key: "wip", text: "otevřeno", reason: "", next: "", derived: true });
    expect(j("tk_4").summary.key).toBe("blocked");
    expect(judgementOf({ state: "awaiting_checks", stateLabel: "čeká", next: "CI ověří HEAD" }).summary).toMatchObject({ key: "checking", text: "čeká", next: "CI ověří HEAD" });
    expect(judgementOf({}).summary.key).toBe("unknown");
    expect([j("tk_2").allowed, j("tk_2").axes, board.balls[1].openPr]).toEqual([[], null, false]);
  });
});

describe("snímek a stáří zdrojů", () => {
  it("čte snímek; bez něj null", () => {
    expect(board.snapshot).toMatchObject({ id: "snap_28", builtAt: "2026-11-06T10:05:00Z" });
    expect(board.snapshot!.sources.map((s) => s.name)).toEqual(["git", "prs", "checks", "sessions", "deploy"]);
    expect(snapshotOf(undefined)).toBeNull();
    expect(sourceAges(null, now)).toEqual([]);
  });
  it("každý zdroj zvlášť; ≥ 10 min, ok:false nebo bez času = zastaralé", () => {
    expect(sourceAges(board.snapshot, now)).toEqual([
      { name: "git", text: "git před 2 min", stale: false },
      { name: "prs", text: "PR (GitHub) před 26 min · zastaralé", stale: true },
      { name: "checks", text: "kontroly před 3 min", stale: false },
      { name: "sessions", text: "relace před 4 min", stale: false },
      { name: "deploy", text: "nasazení nikdy · zastaralé", stale: true },
    ]);
    // stáří se počítá od verifiedAt, ne od načtení: o 8 min později je git zastaralý
    expect(sourceAges(board.snapshot, now + 8 * 60000)[0].stale).toBe(true);
    expect([ago("", now), ago("2026-11-06T10:05:50Z", now), ago("2026-11-06T06:00:00Z", now)]).toEqual(["nikdy", "právě teď", "před 4 h"]);
    expect(hhmm("")).toBe("—");
  });
});

describe("akce panelu", () => {
  it("povolené jako tlačítka, zakázané s důvodem; bez API a bez plné revize zakázané", () => {
    expect(actionsOf(j("tk_1"), "")).toEqual([
      { id: "merge", label: "Začlenit", enabled: true, why: "" },
      { id: "block", label: "Blokovat", enabled: true, why: "" },
      { id: "accept", label: "Přijmout", enabled: false, why: "acceptance.accepted(HEAD) – už přijato" },
    ]);
    const pending = judgementOf({ allowed: ["accept", "unblock"], blocked: { merge: "acceptance.pending – nejdřív přijetí" } });
    expect(actionsOf(pending, "").map((a) => [a.id, a.enabled, a.why])).toEqual([
      ["accept", false, "načítám plnou revizi HEAD z detailu"], ["unblock", false, "operace zatím bez API (L7 PR 5)"], ["merge", false, "acceptance.pending – nejdřív přijetí"]]);
    expect(actionsOf(pending, "1aebfc1a2b3c")[0]).toEqual({ id: "accept", label: "Přijmout 1aebfc1", enabled: true, why: "" });
    expect(actionsOf(j("tk_2"), "abc")).toEqual([]);
  });
});

describe("výrok Pletora", () => {
  it("skládá jen osy a souhrn, se zdrojem a stářím", () => {
    expect(pletorVerdict("OP-3F9A1C", j("tk_1"), board.snapshot, now)).toEqual([
      "OP-3F9A1C přijato, čeká na začlenění 9c8050f.",
      "Kontroly revize 9c8050f prošly (CI, před 3 min).",
      "Přijato pro 9c8050f.",
      "Začlenění ani nasazení potvrzené nemám.",
      "Stav PR neznám (GitHub před 26 min).",
    ]);
  });
  it("začleněno bez záznamu způsobu, nasazení, chybějící kontroly", () => {
    const merged = judgementOf({ summary: { key: "merged", text: "začleněno" }, axes: { checks: { state: "missing" }, integration: { state: "merged", target: "develop", sha: "abcdef0123" }, deploy: { envs: {} } } });
    expect(pletorVerdict("L5", merged, null, now)).toEqual(["L5 začleněno.", "Kontroly pro aktuální revizi chybí.", "Začleněno do develop (abcdef0, způsob neověřen). Nasazení potvrzené nemám."]);
    const deployed = judgementOf({ summary: { text: "začleněno" }, axes: { integration: { state: "merged", target: "main", sha: "abcdef0123", mode: "squash" }, deploy: { envs: { prod: "d8da63b9" } } } });
    expect(pletorVerdict("L4", deployed, null, now).slice(1)).toEqual(["Stav kontrol neznám.", "Začleněno do main (abcdef0, squash).", "Běží: prod@d8da63b."]);
  });
  it("bez os přizná, že má jen text stavu", () => {
    expect(pletorVerdict("Datový uzel", j("tk_2"), null, now)).toEqual(["Datový uzel otevřeno.", "Osy s důkazy backend zatím neposlal; řídím se jen textem stavu."]);
  });
});
