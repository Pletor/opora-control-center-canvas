import { describe, expect, it } from "vitest";
import {
  AGENT_CATEGORIES,
  AGENT_DRAG_TYPE,
  AGENT_ITEMS,
  agentCatalogLint,
  agentItemById,
  agentItemsOf,
  searchAgentItems,
  startAgentDrag,
  type AgentItem,
} from "./agent-catalog";

/** Zkušební položka: základ, ke kterému se v testu dopisuje jen to, co se zkouší. */
const fixture = (patch: Partial<AgentItem>): AgentItem => ({
  id: "fixture",
  category: "rules",
  label: "Zkušební položka",
  hint: "Jen pro test",
  icon: "×",
  kind: "rule",
  rules: { must: ["Musí"], mustNot: [] },
  decomposition: [{ title: "Krok", text: "Popis" }],
  template: "1. Krok jedna.",
  endCriteria: "Hotovo, když krok proběhne.",
  stopCondition: "Zastav, když chybí vstup.",
  refs: [],
  ...patch,
});

describe("agent-catalog – katalog jako data", () => {
  it("žádná kategorie není prázdná", () => {
    for (const category of AGENT_CATEGORIES) {
      expect(agentItemsOf(category.id).length, category.label).toBeGreaterThan(0);
    }
    expect(AGENT_CATEGORIES.map((c) => c.id)).toEqual(["workflows", "pipelines", "rules", "hooks", "skills", "agents"]);
  });

  it("id položek jsou jedinečná a každá patří do známé kategorie", () => {
    const ids = AGENT_ITEMS.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
    const known = new Set(AGENT_CATEGORIES.map((c) => c.id));
    expect(AGENT_ITEMS.filter((item) => !known.has(item.category))).toEqual([]);
  });

  it("každá položka nese aspoň jedno pravidlo, jeden krok rozpadu, šablonu, kritérium konce a stop podmínku", () => {
    for (const item of AGENT_ITEMS) {
      expect(item.rules.must.length, item.id).toBeGreaterThan(0);
      expect(item.decomposition.length, item.id).toBeGreaterThan(0);
      expect(item.template.trim().length, item.id).toBeGreaterThan(0);
      expect(item.endCriteria.trim().length, item.id).toBeGreaterThan(0);
      expect(item.stopCondition.trim().length, item.id).toBeGreaterThan(0);
      expect(item.label.trim().length, item.id).toBeGreaterThan(0);
      expect(item.hint.trim().length, item.id).toBeGreaterThan(0);
      expect(item.icon.trim().length, item.id).toBeGreaterThan(0);
    }
  });

  it("agentItemsOf vrací jen svou kategorii a agentItemById najde položku z tažení", () => {
    expect(agentItemsOf("agents").every((item) => item.category === "agents")).toBe(true);
    expect(agentItemById("wf-five-phases")?.label).toBe("Zadání → hotovo v pěti fázích");
    expect(agentItemById("neexistuje")).toBeNull();
  });

  it("každá pipeline odkazuje aspoň na jednu položku levého katalogu", () => {
    for (const item of agentItemsOf("pipelines")) {
      expect(item.refs.length, item.id).toBeGreaterThan(0);
    }
  });
});

describe("agent-catalog – hledání bez diakritiky", () => {
  it("najde „Pravidla“ na dotaz „pravidlo“", () => {
    const found = searchAgentItems(AGENT_ITEMS, "pravidlo");
    expect(found.length).toBeGreaterThan(0);
    expect(found.every((item) => item.category === "rules")).toBe(true);
  });

  it("hledá bez diakritiky i v nápovědě (příkazy → prikazy)", () => {
    const found = searchAgentItems(AGENT_ITEMS, "prikazy");
    expect(found.map((item) => item.id)).toContain("hook-verify-gates");
  });

  it("prázdný dotaz nechává katalog beze změny, neznámý dotaz nevrátí nic", () => {
    expect(searchAgentItems(AGENT_ITEMS, "  ")).toBe(AGENT_ITEMS);
    expect(searchAgentItems(AGENT_ITEMS, "xyzxyzxyz").length).toBe(0);
  });
});

describe("agent-catalog – lint kontraktu (kritérium konce, stop podmínka, refs, fáze)", () => {
  it("vydaný katalog je čistý", () => {
    expect(agentCatalogLint()).toEqual([]);
  });

  it("chytí chybějící stop podmínku", () => {
    const bad = fixture({ id: "bez-stop", stopCondition: "" });
    const violations = agentCatalogLint([bad]);
    expect(violations).toEqual([{ itemId: "bez-stop", rule: "stop", detail: expect.any(String) }]);
  });

  it("chytí chybějící kritérium konce", () => {
    const bad = fixture({ id: "bez-konce", endCriteria: "   " });
    const violations = agentCatalogLint([bad]);
    expect(violations).toEqual([{ itemId: "bez-konce", rule: "end", detail: expect.any(String) }]);
  });

  it("chytí odkaz na neexistující položku levého katalogu", () => {
    const bad = fixture({ id: "spatny-ref", refs: ["neexistuje-v-leve-knihovne"] });
    const violations = agentCatalogLint([bad]);
    expect(violations).toEqual([{ itemId: "spatny-ref", rule: "ref", detail: expect.any(String) }]);
  });

  it("chytí workflow bez všech pěti fází v šabloně", () => {
    const bad = fixture({ id: "neuplny-workflow", kind: "workflow", template: "1. discover — jen tohle." });
    const violations = agentCatalogLint([bad]);
    expect(violations).toEqual([
      { itemId: "neuplny-workflow", rule: "template", detail: expect.stringContaining("define") },
    ]);
  });

  it("chytí chybějící šablonu", () => {
    const bad = fixture({ id: "bez-sablony", template: "   " });
    const violations = agentCatalogLint([bad]);
    expect(violations).toEqual([{ itemId: "bez-sablony", rule: "template", detail: expect.any(String) }]);
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
