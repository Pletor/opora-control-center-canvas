import { describe, expect, it } from "vitest";
import { AGENT_CATEGORIES } from "@/editor/component-library/agent-catalog/logic/agent-catalog";
import { iconPath } from "@/ui-kit/icon/logic/icon-paths";
import {
  AGENT_NAVBAR_KEY,
  categoryIcon,
  emptyAgentNavbar,
  isCollapseShortcut,
  parseAgentNavbar,
  readState,
  setCategory,
  setQuery,
  setTab,
  stepsBadge,
  stepsLine,
} from "./agent-navbar";

describe("agent-navbar – stav panelu", () => {
  it("začíná na kategorii Workflows a na záložce Katalog; viditelnost nenese", () => {
    expect(emptyAgentNavbar()).toEqual({ category: "workflows", query: "", tab: "catalog" });
  });

  it("výběr kategorie mění jen kategorii, nic nerozbaluje", () => {
    expect(setCategory(emptyAgentNavbar(), "skills")).toEqual({
      category: "skills",
      query: "",
      tab: "catalog",
    });
  });

  it("kategorie, hledání a záložka se navzájem nemažou", () => {
    const state = setQuery(setCategory(emptyAgentNavbar(), "hooks"), "commit");
    const onAgents = setTab(state, "agents");
    expect(onAgents).toEqual({ ...state, tab: "agents" });
    expect(setTab(onAgents, "catalog").query).toBe("commit");
    expect(setCategory(onAgents, "rules")).toMatchObject({ tab: "agents", query: "commit", category: "rules" });
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

  it("starší preference s `collapsed` se ignoruje: po načtení je panel vždy zavřený", () => {
    expect(parseAgentNavbar(JSON.stringify({ collapsed: false }))).toEqual(emptyAgentNavbar());
    expect(parseAgentNavbar(JSON.stringify({ collapsed: true, tab: "hook" }))).not.toHaveProperty("collapsed");
  });

  it("uložený stav se vrátí celý a dlouhý dotaz se usekne", () => {
    const stored = JSON.stringify({ category: "agents", query: "x".repeat(300), tab: "agents" });
    expect(parseAgentNavbar(stored)).toEqual({
      category: "agents",
      query: "x".repeat(120),
      tab: "agents",
    });
  });

  it("prostředí bez localStorage (test, soukromé okno) dostane výchozí stav místo výjimky", () => {
    expect(readState()).toEqual(emptyAgentNavbar());
  });
});

describe("agent-navbar – zkratka Ctrl+Shift+. (posluchač drží panel-dock)", () => {
  const key = (over: Partial<Parameters<typeof isCollapseShortcut>[0]>) =>
    ({ key: ".", ctrlKey: true, metaKey: false, shiftKey: true, altKey: false, ...over });

  it("Ctrl+Shift+. i ⌘⇧. panel přepnou, a to i když rozložení pošle „>“", () => {
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
