import { describe, expect, it } from "vitest";
import type { AgentCardStage } from "@/hub/oporahub-agent-state/logic/agent-state";
import { cardFace } from "./card-face";
import { faceCounter, faceKind, facePill } from "./face-family";

const face = (extra: Partial<AgentCardStage> | null = {}) => cardFace({ nodeId: "a", sector: false, decisions: [], nameOf: id => id,
  card: extra ? { nodeId: "a", stage: "plan", health: "ok", reason: "card_in_plan", executionId: null, ...extra } : undefined });

describe("druh a kód karty", () => {
  it("předpona v názvu dá druh, pořadí dá číslo kódu", () => {
    expect(faceKind({ nodeId: "n1", type: "research", sector: false, order: 144 })).toEqual({ family: "work", word: "Výzkum", code: "E-144" });
    expect(faceKind({ nodeId: "n1", type: "gate", sector: false, order: 7 })).toMatchObject({ family: "verify", code: "V-7" });
    expect(faceKind({ nodeId: "n1", type: "grilling", sector: false })).toMatchObject({ family: "decision", word: "Rozhodnutí" });
  });

  it("doménová role kontraktu bez předpony je kontrakt; předpona má přednost", () => {
    expect(faceKind({ nodeId: "n1", type: null, element: "api_contract", sector: false, order: 12 })).toEqual({ family: "contract", word: "Kontrakt", code: "C-12" });
    expect(faceKind({ nodeId: "n1", type: "task", element: "api_contract", sector: false }).word).toBe("Úkol");
  });

  it("co nejde odvodit, je neutrální krok s kódem ze začátku id", () => {
    expect(faceKind({ nodeId: "a1b2-c3d4", type: null, sector: false })).toEqual({ family: "work", word: "Krok", code: "E-A1B2" });
    expect(faceKind({ nodeId: "s9", type: null, sector: true, order: null }).word).toBe("Sektor");
  });
});

describe("pilulka a počitadlo", () => {
  it("stav tváře se přeloží do slova návrhu", () => {
    expect(facePill(face(null))).toEqual({ tone: "prep", word: "V přípravě" });
    expect(facePill(face({ stage: "plan_writeback", reason: "card_closed" }))).toEqual({ tone: "done", word: "Hotovo" });
    expect(facePill(face({ stage: "work", lease: { holder: "agent:x", expiresAt: "2026-11-11T10:00:00Z", epoch: 1 } })).word).toBe("V realizaci");
    expect(facePill(face({ stage: "claim" })).word).toBe("Přijatý");
  });

  it("počitadlo skloňuje kroky a bez kroků mlčí", () => {
    expect(faceCounter(face({ steps: { total: 4, done: 2, current: null } }))).toBe("2/4 kroky");
    expect(faceCounter(face({ steps: { total: 5, done: 0, current: null } }))).toBe("0/5 kroků");
    expect(faceCounter(face(null))).toBe("");
  });
});
