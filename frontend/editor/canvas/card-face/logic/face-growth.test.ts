import { describe, expect, it } from "vitest";
import type { AgentCardStage } from "@/hub/oporahub-agent-state/logic/agent-state";
import { cardFace } from "./card-face";
import { faceGrowth } from "./face-growth";

const face = (extra: Partial<AgentCardStage> | null = {}) => cardFace({ nodeId: "a", sector: false, decisions: [], nameOf: id => id,
  card: extra ? { nodeId: "a", stage: "plan", health: "ok", reason: "card_in_plan", executionId: null, ...extra } : undefined });

describe("růst karty", () => {
  it("karta jen v plánu je semínko; bez záměru i kroků Z chybí a kruh nemá číslo", () => {
    expect(faceGrowth(face(null), "")).toEqual({ shape: "seed", label: "semínko", percent: null,
      truths: ["miss", "wait", "miss", "wait"], live: false });
    expect(faceGrowth(face(), "Zákazník zaplatí kartou.").truths[0]).toBe("ok");
  });

  it("běžící lease je pupen s pulzem a podílem kroků", () => {
    const growth = faceGrowth(face({ stage: "work", reason: "runs_active", executionId: "e1",
      lease: { holder: "agent:x", expiresAt: "2026-11-11T10:00:00Z", epoch: 1 }, steps: { total: 4, done: 1, current: "s2" } }), "");
    expect(growth).toMatchObject({ shape: "bud", percent: 25, live: true, truths: ["ok", "wait", "miss", "wait"] });
  });

  it("uzavřená karta je list: sto procent a S svítí", () => {
    expect(faceGrowth(face({ stage: "plan_writeback", reason: "card_closed" }), "")).toMatchObject({ shape: "leaf", percent: 100,
      truths: ["miss", "wait", "ok", "wait"] });
  });

  it("tečka K nese zrcadlo kódu: ok/part/bad, bez měření nebo neznámá hodnota čeká", () => {
    expect(faceGrowth(face({ mirror: "ok" }), "").truths[1]).toBe("ok");
    expect(faceGrowth(face({ mirror: "part" }), "").truths[1]).toBe("part");
    expect(faceGrowth(face({ mirror: "bad" }), "").truths[1]).toBe("bad");
    expect(faceGrowth(face({ mirror: null }), "").truths[1]).toBe("wait");
    expect(faceGrowth(face({ mirror: "weird" as never }), "").truths[1]).toBe("wait");
  });

  it("tečka B nese verdikt budoucnosti: clean/warning/blocked, jinak čeká", () => {
    expect(faceGrowth(face({ future: "clean" }), "").truths[3]).toBe("ok");
    expect(faceGrowth(face({ future: "warning" }), "").truths[3]).toBe("part");
    expect(faceGrowth(face({ future: "blocked" }), "").truths[3]).toBe("bad");
    expect(faceGrowth(face({ future: null }), "").truths[3]).toBe("wait");
  });

  it("návrh je fialový i bez kroků; bez zrcadla K i B čekají", () => {
    const growth = faceGrowth(face({ stage: "proposal" }), "x");
    expect(growth.shape).toBe("prop");
    expect([growth.truths[1], growth.truths[3]]).toEqual(["wait", "wait"]);
  });
});
