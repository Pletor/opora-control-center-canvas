import { describe, expect, it } from "vitest";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import { parseAgentState, type AgentGuardFinding } from "@/hub/oporahub-agent-state/logic/agent-state";
import { guardFindings, guardLine, parseGuardStatus, type GuardStatusItem } from "./velin-guards";

const zero = { block: 0, warn: 0, info: 0 };
const guard = (id: string, extra: Partial<GuardStatusItem> = {}): GuardStatusItem =>
  ({ id, label: id, every_s: 30, lastRunAt: "2026-10-28T09:00:00+00:00", lastOkAt: null, open: zero, ...extra });
const finding = (key: string, extra: Partial<AgentGuardFinding> = {}): AgentGuardFinding => ({ key, guard: "prace", rule: "work.no-heartbeat",
  severity: "warn", message: `Nález ${key}`, workspaceId: "draft", firstSeen: "2026-10-28T09:00:00+00:00", lastSeen: "2026-10-28T09:00:00+00:00", ...extra });

describe("Řádek strážců", () => {
  it("✓ jen bez chyby a bez nálezu block/warn mimo mapu; mapa ani info se nepočítají", () => {
    const status = { guards: [guard("mapa", { open: { block: 4, warn: 9, info: 0 } }), guard("prace", { open: { ...zero, info: 2 } })], open: zero };
    expect(guardLine(status)).toEqual({ ok: true, count: 0, lastRunAt: "2026-10-28T09:00:00+00:00", errors: [] });
  });

  it("⚠ N sčítá block a warn ostatních strážců, chyba strážce řádek také rozsvítí", () => {
    const status = { guards: [guard("cesty", { open: { block: 1, warn: 2, info: 0 }, lastRunAt: "2026-10-28T09:05:00+00:00" }),
      guard("pravda", { lastError: "ValueError: git" })], open: zero };
    const line = guardLine(status);
    expect(line).toMatchObject({ ok: false, count: 3, lastRunAt: "2026-10-28T09:05:00+00:00" });
    expect(line.errors).toEqual([{ id: "pravda", label: "pravda", error: "ValueError: git" }]);
    expect(guardLine({ guards: [guard("pravda", { lastError: "x" })], open: zero }).ok).toBe(false);
  });

  it("neplatnou odpověď serveru nebere", () => {
    expect(parseGuardStatus({ guards: [guard("prace")], open: zero })).not.toBeNull();
    expect(parseGuardStatus({ guards: [{ id: "x" }], open: zero })).toBeNull();
    expect(parseGuardStatus(null)).toBeNull();
  });
});

describe("Nálezy strážců z agent-state", () => {
  it("drží pořadí serveru, doplní jméno karty a strážce mapy vynechá", () => {
    const state = agentStateFixture({ guards: { open: { block: 1, warn: 1, info: 0 }, findings: [
      finding("j", { guard: "cesty", severity: "block", nodeId: "a" }), finding("m", { guard: "mapa", nodeId: "a" }), finding("t", { guard: "pravda" })] } });
    expect(guardFindings(state, id => id.toUpperCase())?.map(item => [item.key, item.cardName])).toEqual([["j", "A"], ["t", ""]]);
    expect(guardFindings(agentStateFixture({}), id => id)).toBeNull();
  });

  it("parser agent-state přijme guards i guardFindings karty a odmítne neznámou závažnost", () => {
    const base = agentStateFixture({ cards: [{ nodeId: "a", stage: "plan", health: "ok", reason: "card_in_plan", executionId: null,
      guardFindings: { count: 2, severity: "block" } }], guards: { open: { block: 1, warn: 0, info: 0 }, findings: [finding("j", { severity: "block" })] } });
    const raw = JSON.parse(JSON.stringify(base));
    expect(parseAgentState(raw, "draft", "draft").guards?.findings).toHaveLength(1);
    raw.guards.findings[0].severity = "fatal";
    expect(() => parseAgentState(raw, "draft", "draft")).toThrow("nálezy strážců");
    const card = JSON.parse(JSON.stringify(base));
    card.cards[0].guardFindings.severity = "fatal";
    expect(() => parseAgentState(card, "draft", "draft")).toThrow("etapy karet");
  });
});
