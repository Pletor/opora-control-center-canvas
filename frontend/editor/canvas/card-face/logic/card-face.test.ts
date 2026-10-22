import { describe, expect, it } from "vitest";
import type { AgentCardStage } from "@/hub/oporahub-agent-state/logic/agent-state";
import { cardFace } from "./card-face";
import { countdown, gateWord, shortReason } from "./face-labels";

const card = (extra: Partial<AgentCardStage> = {}): AgentCardStage => ({
  nodeId: "a", stage: "plan", health: "ok", reason: "card_in_plan", executionId: null, ...extra,
});
const face = (extra: Partial<AgentCardStage> = {}, decisions = [] as Parameters<typeof cardFace>[0]["decisions"]) =>
  cardFace({ nodeId: "a", card: card(extra), sector: false, decisions, nameOf: id => id.toUpperCase() });

describe("tvář karty", () => {
  it("blokovaná předchůdcem: čárkovaná, jeden řádek a patička s předchůdci", () => {
    const view = face({ blockedBy: ["b", "c"], steps: { total: 6, done: 0, current: null } });
    expect(view.state).toBe("blocked");
    expect([view.chip.word, view.stage, view.reason]).toEqual(["blokováno", "plán", "čeká na 2"]);
    expect(view.footer).toEqual({ kind: "blocked", ids: ["b", "c"], text: "B, C" });
    expect(view.steps).toMatchObject({ count: "0/6", label: "kroky čekají" });
  });

  it("agent pracuje: holder z lease, aktuální segment a název kroku", () => {
    const view = face({ stage: "work", reason: "runs_active", executionId: "e1",
      lease: { holder: "agent:codex-2", expiresAt: "2026-10-22T10:00:00Z", epoch: 3 },
      steps: { total: 7, done: 3, current: "s4", currentTitle: "Obnova po výpadku" } });
    expect(view.state).toBe("working");
    expect(view.holder).toEqual({ who: "agent", name: "codex-2" });
    expect(view.steps.segments).toEqual(["done", "done", "done", "cur", "", "", ""]);
    expect(view.steps.label).toBe("s4 Obnova po výpadku");
  });

  it("rozhodnutí člověka má přednost a patička nese otázku", () => {
    const view = face({ stage: "acceptance", health: "waiting", reason: "x" },
      [{ id: "d", kind: "accept", targetId: "a", title: "Přijmout změnu zadání?", actionId: "act" }]);
    expect(view.state).toBe("decision");
    expect(view.chip).toEqual({ tone: "hum", glyph: "◷", word: "čeká na tebe" });
    expect(view.footer).toMatchObject({ kind: "decision", text: "Přijmout změnu zadání?" });
  });

  it("review s bránou: pravidlo, které drží, a patička brány", () => {
    const view = face({ stage: "review", health: "waiting", reason: "required_checks_pending",
      gate: { status: "pending", rule: "required_checks_pending" }, steps: { total: 6, done: 6, current: null } });
    expect(view.state).toBe("review");
    expect(view.chip.word).toBe("drží");
    expect(view.footer).toMatchObject({ kind: "gate", tone: "warn", text: "CI běží" });
    expect(view.steps.label).toBe("všechny kroky splněny");
  });

  it("hotová, připravená a neznámá karta", () => {
    expect(face({ stage: "plan_writeback", reason: "card_closed" })).toMatchObject({ state: "done", stage: "uzavřeno" });
    expect(face({ stage: "claim", reason: "cards_ready" })).toMatchObject({ state: "ready", stage: "k převzetí" });
    const unknown = cardFace({ nodeId: "z", sector: true, decisions: [], nameOf: String });
    expect(unknown).toMatchObject({ state: "plan", kindChip: "sektor", reason: "mimo OporaHub" });
    expect(unknown.steps.label).toBe("plán bez kroků");
  });

  it("dlouhý plán se kreslí nejvýš dvanácti segmenty", () => {
    expect(face({ steps: { total: 30, done: 15, current: "s16" } }).steps.segments).toHaveLength(12);
  });
});

describe("popisky", () => {
  it("neznámý kód zůstává doslova, brána bez pravidla podle stavu", () => {
    expect(shortReason("x_unknown")).toBe("x_unknown");
    expect(gateWord({ status: "blocked", rule: null })).toBe("blokuje");
    expect(gateWord({ status: "ready", rule: "x" })).toBe("splněna");
  });

  it("odpočet lease", () => {
    const now = Date.parse("2026-10-22T10:00:00Z");
    expect(countdown("2026-10-22T10:04:12Z", now)).toBe("04:12");
    expect(countdown("2026-10-22T11:00:01Z", now)).toBe("1:00:01");
    expect(countdown("2026-10-22T09:00:00Z", now)).toBe("vypršel");
  });
});
