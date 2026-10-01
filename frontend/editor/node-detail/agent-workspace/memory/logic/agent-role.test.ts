import { describe, expect, it } from "vitest";
import { emptyDesktopState, emptyNodeWorkflow, type DesktopState } from "@/shared/desktop-state/logic/types";
import { agentRoleOf, setAgentRole } from "./agent-role";

const withNodes = (nodes: DesktopState["nodes"]): DesktopState => ({ ...emptyDesktopState(), nodes });

describe("agent-role: čtení role karty", () => {
  it("uzel bez role i neznámá karta se čtou jako bez role", () => {
    expect(agentRoleOf(emptyDesktopState(), "n1")).toBeNull();
    expect(agentRoleOf(withNodes({ n1: emptyNodeWorkflow() }), "n1")).toBeNull();
  });

  it("uložená role se vrátí beze změny", () => {
    const state = withNodes({ n1: { ...emptyNodeWorkflow(), agentRole: "role-frontend" } });
    expect(agentRoleOf(state, "n1")).toBe("role-frontend");
  });

  it("prázdný řetězec není role", () => {
    expect(agentRoleOf(withNodes({ n1: { ...emptyNodeWorkflow(), agentRole: "" } }), "n1")).toBeNull();
  });
});

describe("agent-role: mutace role karty", () => {
  it("role se uloží na uzel a zbytek stavu zůstane netknutý", () => {
    const state = withNodes({
      n1: { ...emptyNodeWorkflow(), phase: "build" },
      n2: { ...emptyNodeWorkflow(), agentRole: "role-db" },
    });
    const next = setAgentRole("n1", "role-frontend")(state);
    expect(next.nodes.n1.agentRole).toBe("role-frontend");
    expect(next.nodes.n1.phase).toBe("build");
    expect(next.nodes.n2).toBe(state.nodes.n2);
    // Původní stav se nepřepisuje: rollback po neúspěšném uložení se má kam vrátit.
    expect(next.nodes.n1).not.toBe(state.nodes.n1);
    expect(state.nodes.n1.agentRole).toBeNull();
  });

  it("karta, která ve stavu ještě není, dostane prázdný uzel s rolí", () => {
    const next = setAgentRole("nova", "role-tests")(emptyDesktopState());
    expect(next.nodes.nova).toEqual({ ...emptyNodeWorkflow(), agentRole: "role-tests" });
  });

  it("prázdná volba roli sundá, nikdy neuloží prázdný řetězec", () => {
    const state = withNodes({ n1: { ...emptyNodeWorkflow(), agentRole: "role-db" } });
    expect(setAgentRole("n1", "")(state).nodes.n1.agentRole).toBeNull();
    expect(setAgentRole("n1", null)(state).nodes.n1.agentRole).toBeNull();
  });
});
