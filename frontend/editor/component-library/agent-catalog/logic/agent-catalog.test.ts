import { describe, expect, it } from "vitest";
import {
  AGENT_CATEGORIES,
  AGENT_DRAG_TYPE,
  AGENT_ITEMS,
  agentCatalogLint,
  agentItemById,
  agentItemsOf,
  agentRelatesLines,
  searchAgentItems,
  startAgentDrag,
  type AgentItem,
} from "./agent-catalog";
import { itemById } from "@/editor/component-library/library-catalog/logic/library-catalog";

/** Zkušební postup: základ, ke kterému se v testu dopisuje jen to, co se zkouší. */
const fixture = (patch: Partial<AgentItem>): AgentItem => ({
  id: "fixture",
  category: "pipelines",
  label: "Zkušební postup",
  purpose: "Jen pro test.",
  kind: "action",
  relates: ["@test-done-gates"],
  invariants: [],
  steps: [{ title: "Krok", text: "Popis" }],
  done: ["Krok proběhl."],
  stopCondition: "Chybí vstup.",
  ...patch,
});

describe("agent-catalog – katalog jako data", () => {
  it("žádná kategorie není prázdná a Hranice nahradily Pravidla", () => {
    for (const category of AGENT_CATEGORIES) {
      expect(agentItemsOf(category.id).length, category.label).toBeGreaterThan(0);
    }
    expect(AGENT_CATEGORIES.map((c) => c.id)).toEqual(["workflows", "pipelines", "agents", "skills", "hooks", "rules"]);
    expect(AGENT_CATEGORIES.find((c) => c.id === "rules")?.label).toBe("Hranice");
    expect(agentItemsOf("rules").map((item) => item.id)).toEqual([
      "rule-no-model-launch",
      "rule-materials-not-commands",
      "rule-no-delete-without-preview",
    ]);
  });

  it("id jsou jedinečná napříč Agenty i Knihovnou", () => {
    const ids = AGENT_ITEMS.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.filter((id) => itemById(id))).toEqual([]);
  });

  it("obecná a duplicitní pravidla zmizela, id pipeline zůstala", () => {
    for (const gone of [
      "rule-no-secrets",
      "rule-tests-before-done-workspace",
      "rule-no-deps-without-consent",
      "rule-tenant-in-every-query",
      "rule-modules-keep-data",
      "rule-service-owns-data",
      "hook-verify-gates",
      "hook-pre-save-lock",
      "skill-selection-general",
    ]) {
      expect(agentItemById(gone), gone).toBeNull();
    }
    expect(agentItemsOf("pipelines").map((item) => item.id)).toEqual([
      "pl-feature-folder",
      "pl-backend-endpoint-cas",
      "pl-verify-before-done",
      "pl-fill-card-via-api",
    ]);
  });

  it("Hranice se táhnou jako pravidlo a každá nese aspoň jednu invariantu", () => {
    for (const item of agentItemsOf("rules")) {
      expect(item.kind, item.id).toBe("rule");
      expect(item.invariants.length, item.id).toBeGreaterThan(0);
    }
  });

  it("souvislosti překládají @id z Agentů i z Knihovny", () => {
    const lines = agentRelatesLines(agentItemById("wf-main-delegates")!);
    expect(lines[0]).toBe(`${agentItemById("agent-main-thread")!.label}: ${agentItemById("agent-main-thread")!.purpose}`);
    const pipeline = agentRelatesLines(agentItemById("pl-verify-before-done")!);
    expect(pipeline).toEqual([`${itemById("test-done-gates")!.label}: ${itemById("test-done-gates")!.purpose}`]);
  });
});

describe("agent-catalog – hledání bez diakritiky", () => {
  it("hledá v popisku i účelu bez diakritiky", () => {
    expect(searchAgentItems(AGENT_ITEMS, "nahled").map((item) => item.id)).toContain("rule-no-delete-without-preview");
    expect(searchAgentItems(AGENT_ITEMS, "  ")).toBe(AGENT_ITEMS);
    expect(searchAgentItems(AGENT_ITEMS, "xyzxyzxyz").length).toBe(0);
  });
});

describe("agent-catalog – lint kontraktu §B3", () => {
  it("vydaný katalog je čistý", () => {
    expect(agentCatalogLint()).toEqual([]);
  });

  it("pipeline potřebuje kroky, 1–3 kritéria hotovo, stop podmínku a odkaz do Knihovny", () => {
    const bad = fixture({ id: "spatna", steps: [], done: [], stopCondition: " ", relates: ["Jen věta."] });
    expect(agentCatalogLint([bad]).map((v) => v.rule)).toEqual(["done", "stop", "steps", "ref"]);
  });

  it("chytí neznámý odkaz a víc než dvě invarianty", () => {
    const bad = fixture({
      id: "moc",
      relates: ["@test-done-gates", "@neexistuje"],
      invariants: [
        { kind: "must", text: "a" },
        { kind: "must", text: "b" },
        { kind: "must", text: "c" },
      ],
    });
    expect(agentCatalogLint([bad]).map((v) => v.rule)).toEqual(["invariants", "ref"]);
  });

  it("chytí workflow, jehož kroky nepojmenují všech pět fází", () => {
    const bad = fixture({ id: "neuplny", category: "workflows", kind: "workflow", steps: [{ title: "discover", text: "jen tohle" }] });
    expect(agentCatalogLint([bad])).toEqual([{ itemId: "neuplny", rule: "phases", detail: expect.stringContaining("define") }]);
  });

  it("agent, skill, hook ani hranice nepotřebují kroky ani hotovo", () => {
    const role = fixture({ id: "role", category: "agents", kind: "agent", steps: undefined, done: undefined, stopCondition: undefined, relates: [] });
    expect(agentCatalogLint([role])).toEqual([]);
  });
});

describe("agent-catalog – zdroj tažení", () => {
  it("do schránky tažení jde jen id položky pod vlastním typem a s kopírováním", () => {
    const written: Record<string, string> = {};
    const transfer = {
      effectAllowed: "none",
      setData: (type: string, value: string) => {
        written[type] = value;
      },
    } as unknown as DataTransfer;
    startAgentDrag(transfer, "wf-five-phases");
    expect(written).toEqual({ [AGENT_DRAG_TYPE]: "wf-five-phases" });
    expect(transfer.effectAllowed).toBe("copy");
  });
});
