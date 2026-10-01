import { describe, expect, it } from "vitest";
import { AGENT_CATEGORIES } from "@/editor/component-library/agent-catalog/logic/agent-catalog";
import { iconPath } from "@/ui-kit/icon/logic/icon-paths";
import {
  AGENT_NAVBAR_KEY,
  AGENT_NAVBAR_TABS,
  categoryIcon,
  emptyAgentNavbar,
  isCollapseShortcut,
  parseAgentNavbar,
  readState,
  sectionCategories,
  setCategory,
  setQuery,
  setTab,
  stepsBadge,
  stepsLine,
} from "./agent-navbar";

describe("agent-navbar – sekce Agenti a Postupy", () => {
  it("Postupy jsou workflows a pipelines, Agenti všechno ostatní a nic se neztratí", () => {
    expect(sectionCategories("flows")).toEqual(["workflows", "pipelines"]);
    const agents = sectionCategories("agents");
    expect(agents).toEqual(expect.arrayContaining(["hooks", "skills", "agents"]));
    expect(agents).not.toContain("workflows");
    expect([...agents, ...sectionCategories("flows")].sort()).toEqual(AGENT_CATEGORIES.map((c) => c.id).sort());
  });

  it("záložky Agentů jsou Katalog | Vybraná karta | Hook", () => {
    expect(AGENT_NAVBAR_TABS.map((tab) => tab.label)).toEqual(["Katalog", "Vybraná karta", "Hook"]);
  });
});

describe("agent-navbar – stav sekcí", () => {
  it("každá sekce začíná na své první kategorii a na záložce Katalog; viditelnost nenese", () => {
    expect(emptyAgentNavbar()).toEqual({
      agents: { category: sectionCategories("agents")[0], query: "" },
      flows: { category: "workflows", query: "" },
      tab: "catalog",
    });
  });

  it("kategorie a hledání jedné sekce nemažou druhou", () => {
    const state = setQuery(setCategory(emptyAgentNavbar(), "flows", "pipelines"), "flows", "commit");
    const agents = setCategory(state, "agents", "skills");
    expect(agents.flows).toEqual({ category: "pipelines", query: "commit" });
    expect(agents.agents).toEqual({ category: "skills", query: "" });
    expect(setTab(agents, "hook")).toMatchObject({ tab: "hook", flows: { query: "commit" } });
  });
});

describe("agent-navbar – jeden klíč pro celou aplikaci", () => {
  it("klíč nenese projekt ani pracovní prostor", () => {
    expect(AGENT_NAVBAR_KEY).toBe("opora:agent-navbar:v1");
  });

  it("poškozená nebo cizí preference spadne na výchozí stav", () => {
    expect(parseAgentNavbar(null)).toEqual(emptyAgentNavbar());
    expect(parseAgentNavbar("{nevalidní")).toEqual(emptyAgentNavbar());
    expect(parseAgentNavbar("null")).toEqual(emptyAgentNavbar());
    expect(parseAgentNavbar(JSON.stringify({ collapsed: "ne", category: "neznama", query: 7, tab: "cizi" }))).toEqual(
      emptyAgentNavbar(),
    );
  });

  it("kategorie z cizí sekce se nepřijme", () => {
    const stored = JSON.stringify({ agents: { category: "workflows" }, flows: { category: "skills" } });
    expect(parseAgentNavbar(stored)).toEqual(emptyAgentNavbar());
  });

  it("starší tvar s jednou kategorií přejde do sekce, do které kategorie patří", () => {
    expect(parseAgentNavbar(JSON.stringify({ category: "pipelines", query: "x", tab: "agents", collapsed: true }))).toEqual({
      ...emptyAgentNavbar(),
      flows: { category: "pipelines", query: "" },
      tab: "agents",
    });
    expect(parseAgentNavbar(JSON.stringify({ category: "skills" })).agents.category).toBe("skills");
  });

  it("uložený stav se vrátí celý a dlouhý dotaz se usekne", () => {
    const stored = JSON.stringify({ agents: { category: "hooks", query: "x".repeat(300) }, flows: { category: "pipelines", query: "a" }, tab: "hook" });
    expect(parseAgentNavbar(stored)).toEqual({
      agents: { category: "hooks", query: "x".repeat(120) },
      flows: { category: "pipelines", query: "a" },
      tab: "hook",
    });
  });

  it("prostředí bez localStorage (test, soukromé okno) dostane výchozí stav místo výjimky", () => {
    expect(readState()).toEqual(emptyAgentNavbar());
  });
});

describe("agent-navbar – zkratka Ctrl+Shift+. (posluchač drží panel-dock)", () => {
  const key = (over: Partial<Parameters<typeof isCollapseShortcut>[0]>) =>
    ({ key: ".", ctrlKey: true, metaKey: false, shiftKey: true, altKey: false, ...over });

  it("Ctrl+Shift+. i ⌘⇧. otevřou Agenty, a to i když rozložení pošle „>“", () => {
    expect(isCollapseShortcut(key({}))).toBe(true);
    expect(isCollapseShortcut(key({ key: ">" }))).toBe(true);
    expect(isCollapseShortcut(key({ ctrlKey: false, metaKey: true }))).toBe(true);
  });

  it("bez modifikátorů, bez Shiftu a s Altem zkratka neplatí", () => {
    expect(isCollapseShortcut(key({ ctrlKey: false }))).toBe(false);
    expect(isCollapseShortcut(key({ shiftKey: false }))).toBe(false);
    expect(isCollapseShortcut(key({ altKey: true }))).toBe(false);
    expect(isCollapseShortcut(key({ key: "," }))).toBe(false);
  });
});

describe("agent-navbar – řádka rozpadu na dlaždici", () => {
  it("skloňuje počet kroků a doplní chybějící kritérium konce", () => {
    expect(stepsLine(1, "test projde")).toBe("1 krok · konec: test projde");
    expect(stepsLine(3, "test projde")).toBe("3 kroky · konec: test projde");
    expect(stepsLine(7, "test projde")).toBe("7 kroků · konec: test projde");
    expect(stepsLine(0, "   ")).toBe("0 kroků · konec: neurčen");
  });

  it("stepsBadge skloňuje stejně, jen bez konce", () => {
    expect(stepsBadge(1)).toBe("1 krok");
    expect(stepsBadge(3)).toBe("3 kroky");
    expect(stepsBadge(7)).toBe("7 kroků");
    expect(stepsBadge(0)).toBe("0 kroků");
  });
});

describe("agent-navbar – ikony kategorií podle kontraktu", () => {
  it("každá kategorie má ikonu z tabulky docs/panely-editoru.md", () => {
    expect(categoryIcon("workflows")).toBe("workflow");
    expect(categoryIcon("pipelines")).toBe("link");
    expect(categoryIcon("rules")).toBe("scale");
    expect(categoryIcon("hooks")).toBe("terminal");
    expect(categoryIcon("skills")).toBe("sparkles");
    expect(categoryIcon("agents")).toBe("users");
  });

  it("neznámá kategorie dostane ikonu workflows, aby lišta nezůstala prázdná", () => {
    expect(categoryIcon("neznama")).toBe("workflow");
    expect(categoryIcon("")).toBe("workflow");
  });

  it("žádná kategorie katalogu nezůstane bez ikony, kterou jde nakreslit", () => {
    for (const category of AGENT_CATEGORIES) {
      expect(iconPath(categoryIcon(category.id)), category.id).not.toBe("");
    }
  });
});
