import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import DuelSection from "./DuelSection";
import DuelTrail from "./DuelTrail";
import DuelOdds from "./DuelOdds";
import DuelList from "./DuelList";
import type { DuelResponse } from "../logic/duel-view";

const render = (type: unknown, props: object) => renderToStaticMarkup(createElement(type as never, props as never));
const data: DuelResponse = {
  duel: {
    fragment: { id: "d1", revision: 3 }, subject: { kind: "fragment", id: "f1" },
    incumbent: { text: "Starý směr", ref: { fragmentId: "f1", revision: 2 } }, challenger: { text: "Nový směr", by: "agent-b" },
    turns: [{ id: "t1", side: "B", kind: "claim", text: "<b>ne HTML</b>", by: "agent-b", evidence: [{ source: "javascript:alert(1)" }, { source: "https://example.org/x", quote: "citace" }] }],
    scores: [{ turnId: "t1", strength: 7, supports: "B" }], status: "grill", decision: null,
  },
  probability: { p: 0.62, logit: 0.49, n: 1, contributions: [{ turnId: "t1", side: "B", kind: "claim", strength: 7, weight: 1, delta: 0.7, reason: "argument B" }] },
  onTurn: [{ side: "A", grillId: null }], rounds: { A: 0, B: 1 }, canDecide: false,
  trajectory: { p: 0.8, slope: 0.3, se: 0.1, n: 4, last: 7, state: "approaching" },
};

describe("duel section", () => {
  it("list view: vision line, empty list and one terminal input with help, no buttons for turns", () => {
    const html = render(DuelSection, { scope: { project: "p", workspace: "w" }, vaultScope: "", items: [], visionKey: "", focus: null, readOnly: false });
    expect(html).toContain('data-testid="vault-duel"');
    expect(html).toContain("Představa:");
    expect(html).toContain("Žádný duel");
    expect(html).toContain('aria-label="Zpráva do duelu"');
    expect(html).toContain("duel: co chceš změnit · představa: …");
    expect(html).toContain("<details");
    expect(html).toContain("další příkazy");
    expect(html).toContain("rozhodni [#syntéza] [keep|adopt|synthesis: důvod]");
    expect(html.match(/<button/g) ?? []).toHaveLength(0);
  });

  it("list shows status and uncalibrated argument strength", () => {
    const html = render(DuelList, { items: [{ id: "1", title: "Duel o tok", status: "grill", p: 0.62, open: true }], onOpen: () => {} });
    expect(html).toContain("síla B 62 %");
    expect(html).not.toContain("P(B");
    expect(html).toContain("Duel o tok");
    expect(html).toContain("výměny");
    expect(html).toContain("62 %");
  });

  it("trail shows A and B, turns as text and only safe links", () => {
    const html = render(DuelTrail, { duel: data.duel });
    expect(html).toContain("A · platný směr · r2");
    expect(html).toContain("B · změna · agent-b");
    expect(html).toContain("&lt;b&gt;ne HTML&lt;/b&gt;");
    expect(html).toContain('title="t1">#1</span>');
    expect(html).not.toContain('href="javascript');
    expect(html).toContain('href="https://example.org/x"');
    expect(html).toContain("skóre 7,0/10 pro B · 1 soudce");
  });

  it("decided duel shows the human override with the rule outcome", () => {
    const html = render(DuelTrail, { duel: { ...data.duel, status: "decided",
      decision: { outcome: "adopt", text: "Nový směr", p: 0.5, by: "human", actor: "human", override: { reason: "zákazník to chce", ruleOutcome: "synthesis" } } } });
    expect(html).toContain("přebito člověkem: zákazník to chce (pravidlo: syntéza)");
    expect(html).toContain("Vyhrál nový směr (B) – stav uplatnění neznámý");
    expect(html).not.toContain("platí od teď");
    expect(html).not.toContain("uplatněno");
    const applied = render(DuelTrail, { duel: { ...data.duel, status: "decided", decision: { outcome: "adopt", text: "Nový směr", applied: true, appliedRevision: 4 } } });
    expect(applied).toContain("Vyhrál nový směr (B) – platí od teď: Nový směr");
    expect(applied).toContain("uplatněno: zadání má nový text");
    expect(applied).not.toContain("pokračují");
    const stale = render(DuelTrail, { duel: { ...data.duel, status: "decided", decision: { outcome: "adopt", text: "Nový směr", applied: false, reason: "předmět se mezitím změnil" } } });
    expect(stale).toContain("Vyhrál nový směr (B), ale neuplatnil se: předmět se mezitím změnil");
    expect(stale).not.toContain("platí od teď");
    expect(stale.match(/předmět se mezitím změnil/g) ?? []).toHaveLength(1);
    const card = render(DuelTrail, { duel: { ...data.duel, subject: { kind: "node", id: "n1" }, status: "decided",
      decision: { outcome: "adopt", text: "Nový směr", applied: false, reason: "kartu upraví člověk nebo agent podle decision.text" } } });
    expect(card).toContain("Vyhrál nový směr (B) – karta se automaticky nemění; uprav ji podle: Nový směr");
    expect(card).not.toContain("neuplatněno");
    const refused = render(DuelTrail, { duel: { ...data.duel, status: "decided", decision: { outcome: "keep", applied: false, reason: "zůstává A" } } });
    expect(refused).toContain("Zůstává A");
    expect(refused).not.toContain("neuplatněno");
  });

  it("odds show P with thresholds, n, on turn, rounds, breakdown and trend", () => {
    const html = render(DuelOdds, { data });
    expect(html).toContain("Síla argumentů pro B (nekalibrovaná)");
    expect(html).toContain('title="Heuristika ze skóre soudců – není pravděpodobnost ani ověření výsledku."');
    expect(html).toContain('aria-label="Síla argumentů pro B (nekalibrovaná) 62 %, prahy 40 % a 75 %"');
    expect(html).not.toContain("P(B");
    expect(html).toContain("62 %");
    expect(html).toContain("left:40%");
    expect(html).toContain("left:75%");
    expect(html).toContain("n 1 hodnocených");
    expect(html).toContain("Na tahu A – napiš: A: &lt;argument&gt;");
    expect(html).toContain('title="t1">#1</span>');
    expect(html).toContain("Kola: A 0/4 · B 1/4");
    expect(html).toContain("+0,70");
    expect(html).toContain("argument B");
    expect(html).toContain("přibližujeme se");
    expect(html).toContain("směřuje k: syntéza");
  });

  it("odds of a decided duel show the decision, not the zone of P", () => {
    const strong = { ...data.probability, p: 0.9, n: 5 };
    const kept = render(DuelOdds, { data: { ...data, probability: strong, onTurn: [], canDecide: false,
      duel: { ...data.duel, status: "decided", decision: { outcome: "keep", by: "human", actor: "human", override: { reason: "x", ruleOutcome: "adopt" } } } } });
    expect(kept).toContain("rozhodnuto: zůstává A (přebito člověkem)");
    expect(kept).not.toContain("směřuje k");
    expect(kept).not.toContain("platí B");
    expect(kept).toContain("duel__odds-p--adopt");
    const applied = render(DuelOdds, { data: { ...data, probability: strong,
      duel: { ...data.duel, status: "decided", decision: { outcome: "adopt", applied: false } } } });
    expect(applied).toContain("n 5 hodnocených · rozhodnuto: vyhrál B, neuplatněno");
    expect(applied).not.toContain("směřuje k");
  });
});
