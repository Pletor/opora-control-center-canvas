import { describe, expect, it } from "vitest";
import { applyWrite, appliedLine, oddsVerdict, decisionLine, lessonNotice, contributionRows, humanSide, onTurnLines, outcomeLine, percent, turnNumbers, turnRef, roundsLabel, scoreLine, scoresOf, signed, sortDuelItems, sortTurns,
  trendLabel, trendLine, zoneOf, type DuelTurn } from "./duel-view";

describe("duel view", () => {
  it("formats percent and signed numbers in Czech", () => {
    expect(percent(0.623)).toBe("62 %");
    expect(percent(null)).toBe("—");
    expect(percent(1.4)).toBe("100 %");
    expect(signed(0.4213)).toBe("+0,42");
    expect(signed(-0.18)).toBe("−0,18");
  });

  it("zones follow the 40 % / 75 % thresholds with n ≥ 3 for adopt", () => {
    expect(zoneOf(0.8, 3)).toBe("adopt");
    expect(zoneOf(0.8, 2)).toBe("synthesis");
    expect(zoneOf(0.4, 5)).toBe("keep");
    expect(zoneOf(0.55, 5)).toBe("synthesis");
  });

  it("trend states in words with P, slope and n", () => {
    expect(trendLabel("approaching")).toBe("přibližujeme se");
    expect(trendLabel("receding")).toBe("oddalujeme se");
    expect(trendLabel("unclear")).toBe("nejasné");
    expect(trendLabel("insufficient")).toBe("málo dat");
    expect(trendLine({ p: 0.72, slope: 0.4, se: 0.1, n: 5, last: 7.5, state: "approaching" }))
      .toBe("Trend představy: přibližujeme se · P 72 % · sklon +0,40 · n 5 · poslední 7,5");
    expect(trendLine({ p: null, slope: null, se: null, n: 1, last: 6, state: "insufficient" })).toBe("Trend představy: málo dat · n 1 · poslední 6,0");
    expect(trendLine(null)).toBe("Trend představy: málo dat.");
  });

  it("sorts turns by time, keeping server order on ties", () => {
    const turns: DuelTurn[] = [
      { id: "b", side: "A", kind: "claim", text: "", at: "2026-10-15T10:02:00Z" },
      { id: "a", side: "B", kind: "claim", text: "", at: "2026-10-15T10:01:00Z" },
      { id: "c", side: "B", kind: "grill", text: "", at: "2026-10-15T10:02:00Z" },
    ];
    expect(sortTurns(turns).map((turn) => turn.id)).toEqual(["a", "b", "c"]);
  });

  it("on turn, rounds, scores and contributions", () => {
    const numbers = turnNumbers([{ id: "t1", side: "A", kind: "claim", text: "" }, { id: "t2", side: "B", kind: "claim", text: "" }, { id: "t3", side: "A", kind: "grill", text: "" }]);
    expect(onTurnLines([{ side: "B", grillId: "t3" }, { side: "A" }], "grill", numbers))
      .toEqual(["Na tahu B: odpověz na #3 – napiš: odpověď #3: …", "Na tahu A – napiš: A: <argument>"]);
    expect(onTurnLines([], "open", numbers)[0]).toContain("kdokoli");
    expect(onTurnLines([], "synthesis", numbers, true)).toContain("Lze rozhodnout – napiš: rozhodni");
    expect(onTurnLines([{ side: "A" }], "decided", numbers, true)).toEqual(["Rozhodnuto, nikdo není na tahu."]);
    expect(turnRef(numbers, "t2")).toBe("#2");
    expect(turnRef(numbers, "0123456789abcdef")).toBe("#012345…");
    expect(roundsLabel({ A: 2, B: 1 })).toBe("Kola: A 2/4 · B 1/4");
    const score = scoresOf([{ turnId: "t1", strength: 6, supports: "B" }, { turnId: "t1", strength: 8, supports: "B" }, { turnId: "t2", strength: 1, supports: "A" }], "t1");
    expect(score).toEqual({ mean: 7, count: 2, supports: "B" });
    expect(scoreLine(score)).toBe("skóre 7,0/10 pro B · 2 soudců");
    expect(scoresOf([], "t1")).toBeNull();
    const rows = contributionRows([
      { turnId: "t1", side: "B", kind: "claim", strength: 6, weight: 1, delta: 0.6, reason: "argument" },
      { turnId: "t2", side: "A", kind: "grill", strength: 9, weight: 1.5, delta: -1.35, reason: "nezodpovězená otázka" },
    ]);
    expect(rows.map((row) => [row.turnId, row.deltaText])).toEqual([["t2", "−1,35"], ["t1", "+0,60"]]);
  });

  it("human side is the side of the human's last A/B turn", () => {
    expect(humanSide([{ id: "1", side: "A", kind: "claim", text: "", actor: "human" }, { id: "2", side: "human", kind: "note", text: "", actor: "human" }])).toBe("A");
    expect(humanSide([{ id: "1", side: "B", kind: "claim", text: "", actor: "agent" }])).toBeNull();
  });

  it("decision line with override and keep without an applied line", () => {
    expect(decisionLine({ outcome: "adopt", p: 0.5, override: { reason: "zákazník to chce", ruleOutcome: "synthesis" } }))
      .toBe("Rozhodnuto: vyhrál B při síle B 50 % · přebito člověkem: zákazník to chce (pravidlo: syntéza)");
    expect(decisionLine({ outcome: "keep", override: { reason: "x", ruleOutcome: null } })).toContain("(pravidlo: ještě nerozhodlo)");
    expect(decisionLine({ outcome: "keep", p: 0.3 })).toBe("Rozhodnuto: zůstává A při síle B 30 %");
    expect(decisionLine({ outcome: "adopt", p: 0.8 })).toBe("Rozhodnuto: vyhrál B při síle B 80 %");
    expect(outcomeLine({ outcome: "keep" })).toBe("Zůstává A");
    expect(outcomeLine({ outcome: "keep", applied: false, reason: "zůstává A" })).toBe("Zůstává A");
    expect(appliedLine({ outcome: "keep", applied: false, reason: "zůstává A" })).toBe("");
  });

  it("outcome says „platí od teď“ only when the server applied it", () => {
    // applied true → platí od teď
    expect(outcomeLine({ outcome: "adopt", text: "Nový tok", applied: true })).toBe("Vyhrál nový směr (B) – platí od teď: Nový tok");
    expect(outcomeLine({ outcome: "adopt", applied: true }, "Text B")).toBe("Vyhrál nový směr (B) – platí od teď: Text B");
    expect(appliedLine({ outcome: "adopt", applied: true, appliedRevision: 5 })).toBe("uplatněno: zadání má nový text");
    // applied true neslibuje, co agenti udělají: jen že zadání má nový text
    expect(appliedLine({ outcome: "adopt", applied: true, appliedRevision: 5 })).not.toContain("pokračují");
    expect(appliedLine({ outcome: "synthesis", applied: true, appliedRevision: 6 })).not.toContain("agenti");
    // applied false → jen důvod doslova, žádné „platí dál A“, důvod jednou
    const refused = { outcome: "adopt" as const, text: "Nový tok", applied: false, reason: "předmět se mezitím změnil" };
    expect(outcomeLine(refused)).toBe("Vyhrál nový směr (B), ale neuplatnil se: předmět se mezitím změnil");
    expect(outcomeLine(refused)).not.toContain("platí");
    expect(appliedLine(refused)).toBe("");
    expect(outcomeLine({ outcome: "adopt", applied: false, reason: "předmět nebo jeho předek je smazaný" }))
      .toBe("Vyhrál nový směr (B), ale neuplatnil se: předmět nebo jeho předek je smazaný");
    expect(outcomeLine({ outcome: "adopt", applied: false, reason: "předmět už má tento text (beze změny)" }))
      .toBe("Vyhrál nový směr (B), ale neuplatnil se: předmět už má tento text (beze změny)");
    // legacy bez applied
    expect(outcomeLine({ outcome: "adopt", text: "Nový tok" })).toBe("Vyhrál nový směr (B) – stav uplatnění neznámý");
    expect(appliedLine({ outcome: "adopt" })).toBe("");
    // předmět je karta
    const card = { outcome: "adopt" as const, text: "Nový tok", applied: false, reason: "kartu upraví člověk nebo agent podle decision.text" };
    expect(outcomeLine(card, "Text B", "node")).toBe("Vyhrál nový směr (B) – karta se automaticky nemění; uprav ji podle: Nový tok");
    expect(appliedLine(card, "node")).toBe("");
    // syntéza
    expect(outcomeLine({ outcome: "synthesis", text: "Obojí", applied: true })).toBe("Syntéza – platí od teď: Obojí");
    expect(outcomeLine({ outcome: "synthesis", text: "Obojí", applied: false, reason: "představa se mezitím změnila" }))
      .toBe("Syntéza vyhrála, ale neuplatnila se: představa se mezitím změnila");
    expect(outcomeLine({ outcome: "synthesis", text: "Obojí" })).toBe("Syntéza: Obojí – stav uplatnění neznámý");
    expect(outcomeLine({ outcome: "synthesis", text: "Obojí", applied: false, reason: "kartu upraví člověk nebo agent podle decision.text" }, undefined, "node"))
      .toBe("Syntéza vyhrála – karta se automaticky nemění; uprav ji podle: Obojí");
  });

  it("lesson notice and immediate refresh from a write", () => {
    expect(lessonNotice({ lessonSkipped: "duel nemá disciplínu" })).toBe("Poučení přeskočeno (duel bez disciplíny).");
    expect(lessonNotice({ lesson: { lesson: "Změna X neobstála." } })).toBe("Poučení zapsáno: Změna X neobstála.");
    expect(lessonNotice({})).toBe("");
    const prev = { duel: { fragment: { id: "d", revision: 1, title: "Duel" }, subject: { kind: "project", id: "p" }, incumbent: { text: "A" },
      challenger: { text: "B" }, turns: [], scores: [], status: "open", decision: null },
      probability: { p: 0.35, logit: 0, n: 0, contributions: [] }, onTurn: [], rounds: { A: 0, B: 0 }, canDecide: false, trajectory: null };
    const next = applyWrite(prev as never, { fragment: { id: "d", revision: 2 }, duel: { ...prev.duel, turns: [{ id: "t", side: "A", kind: "grill", text: "?" }], status: "grill" } as never,
      onTurn: [{ side: "B", grillId: "t" }], rounds: { A: 1, B: 0 }, canDecide: false });
    expect(next.duel.fragment).toEqual({ id: "d", revision: 2, title: "Duel" });
    expect(next.duel.turns).toHaveLength(1);
    expect(next.onTurn).toEqual([{ side: "B", grillId: "t" }]);
    expect(applyWrite(prev as never, {})).toBe(prev);
    const decided = applyWrite(prev as never, { duel: { ...prev.duel, status: "decided", decision: { outcome: "adopt", text: "B" } } as never,
      decision: { outcome: "adopt", text: "B", applied: true, appliedRevision: 4 } });
    expect(decided.duel.decision).toMatchObject({ outcome: "adopt", applied: true, appliedRevision: 4 });
    expect(decided.canDecide).toBe(false);
  });

  it("odds verdict: decided duel tells the decision, never the probability zone", () => {
    const decided = (decision: object, subjectKind = "fragment") => ({ status: "decided", subject: { kind: subjectKind }, decision }) as never;
    // Zóna P říká opak (p 0,9 / n 5 = adopt, p 0,1 = keep) – rozhoduje decision.
    expect(oddsVerdict(decided({ outcome: "adopt", applied: true }), "keep")).toBe("rozhodnuto: vyhrál B, uplatněno");
    expect(oddsVerdict(decided({ outcome: "synthesis", applied: true }), "keep")).toBe("rozhodnuto: syntéza, uplatněna");
    expect(oddsVerdict(decided({ outcome: "adopt", applied: false }), "adopt")).toBe("rozhodnuto: vyhrál B, neuplatněno");
    expect(oddsVerdict(decided({ outcome: "synthesis", applied: false }), "adopt")).toBe("rozhodnuto: syntéza, neuplatněna");
    expect(oddsVerdict(decided({ outcome: "adopt" }), "keep")).toBe("rozhodnuto: vyhrál B, stav uplatnění neznámý");
    expect(oddsVerdict(decided({ outcome: "synthesis" }), "keep")).toBe("rozhodnuto: syntéza, stav uplatnění neznámý");
    expect(oddsVerdict(decided({ outcome: "adopt", applied: false }, "node"), "keep")).toBe("rozhodnuto: vyhrál B, karta se automaticky nemění");
    expect(oddsVerdict(decided({ outcome: "synthesis", applied: false }, "node"), "keep")).toBe("rozhodnuto: syntéza, karta se automaticky nemění");
    expect(oddsVerdict(decided({ outcome: "keep", applied: false }), "adopt")).toBe("rozhodnuto: zůstává A");
    expect(oddsVerdict(decided({ outcome: "keep", override: { reason: "x", ruleOutcome: "adopt" } }), zoneOf(0.9, 5)))
      .toBe("rozhodnuto: zůstává A (přebito člověkem)");
    expect(oddsVerdict(decided({ outcome: "adopt", applied: true, override: { reason: "x", ruleOutcome: "keep" } }), zoneOf(0.1, 5)))
      .toBe("rozhodnuto: vyhrál B, uplatněno (přebito člověkem)");
    // Otevřený duel beze změny: podle zóny.
    expect(oddsVerdict({ status: "grill", subject: { kind: "fragment" }, decision: null } as never, "adopt")).toBe("směřuje k: platí B");
    expect(oddsVerdict({ status: "open", subject: { kind: "fragment" }, decision: null } as never, "synthesis")).toBe("směřuje k: syntéza");
  });

  it("open duels first", () => {
    const items = sortDuelItems([
      { id: "1", title: "x", status: "decided", p: 0.2, open: false },
      { id: "2", title: "y", status: "grill", p: 0.5, open: true },
    ]);
    expect(items.map((item) => item.id)).toEqual(["2", "1"]);
  });
});
