import { describe, expect, it } from "vitest";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import { loopBadge, loopBadges } from "./loop-badges";

const cards = [
  { nodeId: "a", stage: "review" as const, health: "blocking" as const, reason: "open_security_findings", executionId: "e1" },
  { nodeId: "b", stage: "work" as const, health: "ok" as const, reason: "runs_active", executionId: "e2" },
  { nodeId: "x", stage: "plan" as const, health: "ok" as const, reason: "card_in_plan", executionId: null },
];

describe("canvas loop badges", () => {
  it("shows stage, glyph and word for each visible card", () => {
    const badges = loopBadges(agentStateFixture({ cards }), ["a", "b"]);
    expect(badges.map(item => [item.nodeId, item.stageLabel, item.glyph, item.word])).toEqual([
      ["a", "Review", "✕", "blokuje"], ["b", "Práce", "✓", "v pořádku"]]);
  });
  it("explains the reason in Czech in the title, unknown codes verbatim", () => {
    expect(loopBadge(cards[0]).title).toBe("OporaHub · 7. Review · blokuje · Otevřený důležitý bezpečnostní nález blokuje merge.");
    expect(loopBadge({ ...cards[1], reason: "x_new" }).title).toContain("x_new");
  });
  it("draws nothing without cards[] (older server) or without state", () => {
    expect(loopBadges(agentStateFixture(), ["a"])).toEqual([]);
    expect(loopBadges(null, ["a"])).toEqual([]);
  });
});
