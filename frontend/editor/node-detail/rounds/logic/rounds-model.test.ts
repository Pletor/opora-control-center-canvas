import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { cardView } from "@/editor/canvas/node-card/logic/card-model";
import { cardsWithRoundDecisions, decisionRounds, fromRoundLabel, openRoundLabel, roundChips, roundDecisions, roundDigest, roundNumber, roundOffer, type RoundRecord } from "@/editor/node-detail/rounds/logic/rounds-model";
import { emptyNodeWorkflow } from "@/shared/desktop-state/logic/types";
import type { CanvasNode } from "@/shared/types/logic/types";

const proof = (status: string, url = "") => ({ status, url, note: "" });
const record: RoundRecord = {
  schema: "opora.card-round/1", nodeId: "c1", round: 1, openedAt: "", openReason: "", closedAt: "2026-10-09T10:00:00+00:00",
  frozenAt: "2026-10-09T12:00:00+00:00",
  brief: { goal: { goal: "Cíl v1" }, text: "", fragments: [{ fragmentId: "f1", revision: 1, title: "3.1 Zadání", text: "Text v1.", available: true }] },
  done: { confirmed: true, at: "", by: "human", note: "Kolo 1 hotové." },
  pipeline: { profile: "code", items: [
    { id: "w", kind: "work", lens: "", title: "Implementace", status: "passed", note: "Předávka práce.", doneBy: "work-1" },
    { id: "k", kind: "critic", lens: "sly", title: "Kritik: vyčuraný", status: "failed", note: "Chybí test.", doneBy: "sly-1" },
    { id: "k2", kind: "critic", lens: "sly", title: "Kritik: vyčuraný", status: "passed", note: "Opraveno.", doneBy: "sly-2" },
  ] },
  blocks: [{ id: "b1", number: "1", title: "Blok", state: { status: "met", note: "ok" },
    ports: [{ id: "p1", label: "Varianta A", status: "chosen", reason: "Rychlejší." }, { id: "p2", label: "Bez volby" }] },
  { id: "b2", number: "2", title: "Blok 2", state: { status: "open" } }],
  criteria: [{ id: "k1", text: "Testy zelené.", checked: true }, { id: "k2", text: "Dokumentace.", checked: false }],
  decisions: [{ id: "d1", text: "Originál vedle textu.", by: "agent", createdAt: "t" }],
  evidence: { tests: proof("passed"), review: proof("passed", "https://x/r"), merge: proof("passed", "https://x/pr/1"), checksRun: [] },
  ideas: [{ id: "i1", text: "Otevřený", source: "critic:sly", status: "open" }, { id: "i2", text: "Hotový", source: "review", status: "done" }],
  criticFindings: [{ id: "k", kind: "critic", lens: "sly", title: "Kritik: vyčuraný", status: "failed", note: "Chybí test." }],
  errors: { failedStages: [{ kind: "critic", lens: "sly", title: "Kritik: vyčuraný", status: "", note: "Chybí test." }], agentFailures: "Padal import.", agentFixes: "", handoffErrors: [] },
  commits: { realization: { commit: "abc1234", prUrl: "" }, merge: proof("passed", "https://x/pr/1"), touched: ["src/a.py"] },
  agentWorkspace: {}, agentResults: [{ id: "r1abcdef00", agent: "work-1", createdAt: "t", doneProposed: true, note: "" }],
};

describe("kola karty", () => {
  it("přepínač: minulá kola ✓, běžící kolo ●, uzavřené aktuální ✓", () => {
    expect(roundNumber(undefined)).toBe(1);
    expect(roundChips(2, false).map((chip) => chip.label + " " + chip.mark)).toEqual(["v1 ✓", "v2 ●"]);
    expect(roundChips(3, true).map((chip) => chip.mark)).toEqual(["✓", "✓", "✓"]);
    expect(roundChips(2, false).filter((chip) => chip.current).map((chip) => chip.round)).toEqual([2]);
  });

  it("nové kolo nabídne jen u uzavřené karty; výrazně při změně zadání", () => {
    expect(roundOffer(false, false, 2)).toBeNull();
    expect(roundOffer(true, true, 2)).toBeNull();
    expect(roundOffer(true, false, 0)).toBe("manual");
    expect(roundOffer(true, false, 1)).toBe("prominent");
    expect(openRoundLabel(1)).toBe("Otevřít v2 podle nového zadání");
  });

  it("souhrn kola (data pro hlavu karty): postup, chyby, commity a Podněty", () => {
    const digest = roundDigest(record);
    expect([digest.stagesPassed, digest.stages.length, digest.blocksMet, digest.blocks]).toEqual([2, 3, 1, 2]);
    expect(digest.errorCount).toBe(2);
    expect([digest.commit, digest.prUrl, digest.touched]).toEqual(["abc1234", "https://x/pr/1", ["src/a.py"]]);
    expect([digest.ideasOpen, digest.ideasDone]).toEqual([1, 1]);
  });

  it("rozhodnutí kola zůstávají v historii jako kontext; starší záznam bez nich nic neukáže", () => {
    expect(roundDecisions(record)).toEqual([
      { kind: "port", text: "blok 1: „Varianta A“ zvoleno – Rychlejší." },
      { kind: "criterion", text: "Testy zelené." },
      { kind: "decision", text: "Originál vedle textu." },
    ]);
    const older = { ...record, blocks: [{ id: "b1", number: "1", title: "Blok", state: { status: "met" } }], criteria: undefined, decisions: undefined };
    expect(roundDecisions(older)).toEqual([]);
  });

  it("model karty nese číslo kola (tvář na plátně kola neukazuje, žijí v detailu)", () => {
    const node = { id: "c1", parentId: null, kind: "node", name: "Karta", purpose: "", x: 0, y: 0 } as unknown as CanvasNode;
    const first = cardView(node, emptyNodeWorkflow(), 0);
    expect(first.round).toBe(1);
    const second = cardView(node, { ...emptyNodeWorkflow(), round: { number: 2, openedAt: "", by: "human", reason: "nové zadání" } }, 0);
    expect(second.round).toBe(2);
    expect(roundChips(2, false).map((chip) => chip.label + " " + chip.mark).join(" · ")).toBe("v1 ✓ · v2 ●");
  });

  it("rozhodnutí karty z dřívějšího kola nese štítek „z v1“ podle nejstaršího zamrazeného kola", () => {
    const second = { ...record, round: 2, decisions: [...record.decisions!, { id: "d2", text: "Z v2.", by: "human", createdAt: "t" }] };
    const origin = decisionRounds([second, record]);
    expect([origin.get("d1"), origin.get("d2"), origin.get("d3")]).toEqual([1, 2, undefined]);
    expect([fromRoundLabel(1), fromRoundLabel(3), fromRoundLabel(undefined)]).toEqual(["z v1", "z v3", ""]);
    const round = (number: number) => ({ number, openedAt: "", by: "human", reason: "" });
    expect(cardsWithRoundDecisions([{ nodeId: "c2" }, { nodeId: "c1" }, { nodeId: "" }, { nodeId: "c1" }, { nodeId: "c3" }],
      { c1: { round: round(2) }, c2: { round: round(3) }, c3: {} })).toEqual(["c1", "c2"]);
  });
});
