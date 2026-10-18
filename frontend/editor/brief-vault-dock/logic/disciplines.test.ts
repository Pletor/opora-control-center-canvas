import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { coverageOf, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { flatten } from "./vault-dock-model";
import {
  DISCIPLINES, GROUPS, disciplineCounts, disciplineLabel, filterByDiscipline, ideaTarget, liveDisciplines, migrateLegacy,
  parseDiscipline, pickDiscipline, viewOf,
} from "./disciplines";

let seq = 0;
const node = (title: string, extra: Partial<VaultNode> = {}): VaultNode => ({
  id: "d" + ++seq, revision: 1, parentId: null, scopeNodeId: null, ord: 1, kind: "brief", title, stage: "draft", mvp: "none",
  note: "", by: "agent", actor: "agent", at: "", deleted: false, chars: 10, status: "saved", inserted: false, cards: [],
  changedSinceInsert: false, ideas: 0, children: [], ...extra,
});

describe("disciplines", () => {
  it("mirrors the backend table exactly (id, group, label, layer, logic blocks)", () => {
    const source = readFileSync(fileURLToPath(new URL("../../../../backend/editor/brief_vault/brief_vault_disciplines.py", import.meta.url)), "utf-8");
    const rows = [...source.matchAll(/Discipline\("([^"]+)", "([^"]+)", "([^"]+)", (None|"[^"]+"), (True|False)\)/g)]
      .map(([, id, group, label, layer, blocks]) => ({ id, group, label, layer: layer === "None" ? null : layer.slice(1, -1), logicBlocks: blocks === "True" }));
    expect(rows).toHaveLength(17);
    expect(DISCIPLINES).toEqual(rows);
    expect(GROUPS.map((group) => group.label)).toEqual(["Kreslení", "Logika", "Provoz"]);
  });

  it("reads the effective discipline from the server; unknown or missing = unassigned", () => {
    expect(viewOf({ effectiveDiscipline: "be" })).toBe("be");
    expect(viewOf({ effectiveDiscipline: null })).toBe("none");
    expect(viewOf({ effectiveDiscipline: "design" })).toBe("none");
    expect(disciplineLabel("none")).toBe("Nezařazené");
    expect(disciplineLabel("db")).toBe("Databáze a datový model");
  });

  it("filters the tree by discipline and keeps the path to the root", () => {
    const flow = node("Tok objednávky", { effectiveDiscipline: "ux" });
    const rules = node("Výpočet ceny", { discipline: "be", effectiveDiscipline: "be", children: [node("Sleva", { effectiveDiscipline: "be" })] });
    const root = node("Zadání", { discipline: "ux", effectiveDiscipline: "ux", children: [flow, rules] });
    const ux = filterByDiscipline([root], "ux");
    expect(flatten(ux).map((item) => item.node.title)).toEqual(["Zadání", "Tok objednávky"]);
    const be = filterByDiscipline([root], "be");
    expect(flatten(be).map((item) => [item.node.title, !!item.node.offPath])).toEqual([["Zadání", true], ["Výpočet ceny", false], ["Sleva", false]]);
    expect(coverageOf(be).leaves).toBe(1);
    expect(filterByDiscipline([root], "none")).toEqual([]);
  });

  it("counts live brief fragments per discipline and shows only live neurons", () => {
    const old = node("Staré zadání", { children: [node("1"), node("2"), node("výzkum", { kind: "research" })] });
    const root = node("Nové", { effectiveDiscipline: "ux", children: [node("A", { effectiveDiscipline: "ux" }), node("B", { effectiveDiscipline: "api" })] });
    const counts = disciplineCounts([old, root]);
    expect(counts).toEqual({ none: 3, ux: 2, api: 1 });
    const server = DISCIPLINES.map((item) => ({ ...item, live: item.id === "db" ? 4 : 0 }));
    expect(liveDisciplines(server, counts).map((item) => item.id)).toEqual(["ux", "api", "db"]);
  });

  it("remembers the last live choice, otherwise picks the first live discipline with content", () => {
    const live = DISCIPLINES.filter((item) => ["ux", "be"].includes(item.id));
    expect(pickDiscipline("be", live, { be: 0 })).toBe("be");
    expect(pickDiscipline("none", live, {})).toBe("none");
    expect(pickDiscipline("cache", live, { be: 2 })).toBe("be");
    expect(pickDiscipline(null, live, { ux: 0 })).toBe("ux");
    expect(pickDiscipline(null, [], {})).toBe("none");
  });

  it("parses the stored choice and migrates the old two-track key", () => {
    expect(parseDiscipline(JSON.stringify({ discipline: "cloud" }))).toBe("cloud");
    expect(parseDiscipline(JSON.stringify({ discipline: "design" }))).toBeNull();
    expect(parseDiscipline("{rozbité")).toBeNull();
    expect(migrateLegacy(JSON.stringify({ track: "ux" }))).toBe("ux");
    expect(migrateLegacy(JSON.stringify({ track: "logic" }))).toBe("be");
    expect(migrateLegacy(JSON.stringify({ track: "none" }))).toBe("none");
    expect(migrateLegacy(JSON.stringify({ track: "x" }))).toBeNull();
    expect(migrateLegacy(null)).toBeNull();
  });

  it("a fragment from an idea goes under the root of the chosen discipline, or into a new root with a discipline", () => {
    const ux = node("Zadání UX", { effectiveDiscipline: "ux", scopeNodeId: "s" });
    expect(ideaTarget(filterByDiscipline([ux], "ux"), "s", "ux", null)).toEqual({ parentId: ux.id });
    const path = filterByDiscipline([node("Zadání", { effectiveDiscipline: "ux", children: [node("Výpočet", { effectiveDiscipline: "be" })] })], "be");
    expect(ideaTarget(path, "s", "be", null)).toEqual({ scopeNodeId: "s", discipline: "be" });
    expect(ideaTarget([], "", "none", null)).toBeNull();
    expect(ideaTarget([], "", "none", "db")).toEqual({ scopeNodeId: "", discipline: "db" });
  });
});
