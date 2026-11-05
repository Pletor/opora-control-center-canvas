import { describe, expect, it } from "vitest";
import {
  EMPTY, NAME_RE, askSwitch, defaultFile, discard, editSkill, editTool, keep, loadedSkill, loadedTool, measureLine, measured, savedSkill, savedTool,
  skillDirty, toolDirty,
} from "./workshop-state";

const skill = loadedSkill(EMPTY, "deploy", "SKILL.md", "a");
const tool = loadedTool(EMPTY, "sum", "code", "[]");

describe("stav editorů Dílny", () => {
  it("rozepsané je jen když se draft liší od uloženého; uložení ho srovná", () => {
    expect(skillDirty(skill)).toBe(false);
    const edited = editSkill(skill, "ab");
    expect(skillDirty(edited)).toBe(true);
    expect(skillDirty(savedSkill(edited, "ab"))).toBe(false);
    expect(skillDirty(editSkill(edited, "a"))).toBe(false);
    const toolEdited = editTool(tool, { cases: "[1]" });
    expect(toolDirty(toolEdited)).toBe(true);
    expect(toolDirty(savedTool(toolEdited, "code", "[1]"))).toBe(false);
  });

  it("přechod s neuloženou změnou se odloží; Zahodit vrátí uložené a vydá cíl", () => {
    const dirty = editSkill(skill, "zmena");
    const asked = askSwitch(dirty, { kind: "skill", name: "other", path: "SKILL.md" });
    expect(asked.go).toBe(false);
    expect(asked.state.pending).toEqual({ kind: "skill", name: "other", path: "SKILL.md" });
    const done = discard(asked.state);
    expect(done.target).toEqual({ kind: "skill", name: "other", path: "SKILL.md" });
    expect(done.state.pending).toBeNull();
    expect(done.state.skill?.draft).toBe("a");
    expect(keep(asked.state).skill?.draft).toBe("zmena");
  });

  it("rozepsaný skill nebrzdí přepnutí funkce", () => {
    const both = { ...editSkill(skill, "x"), tool: tool.tool };
    expect(askSwitch(both, { kind: "tool", name: "other" }).go).toBe(true);
    const toolDirtyState = editTool(both, { code: "y" });
    const asked = askSwitch(toolDirtyState, { kind: "tool", name: "other" });
    expect(asked.go).toBe(false);
    expect(discard(asked.state).state.tool?.code).toBe("code");
    expect(discard(asked.state).state.skill?.draft).toBe("x");
  });

  it("nová funkce smaže staré měření; řádek výsledku", () => {
    const m = { name: "sum", passed: 3, total: 4, failed: [], durationMs: 12.4, deterministic: false, error: null };
    const withMeasure = measured(tool, m);
    expect(measureLine(m)).toBe("3/4 prošlo · 12 ms");
    expect(loadedTool(withMeasure, "b", "", "").measure).toBeNull();
  });

  it("výchozí soubor a název", () => {
    expect(defaultFile(["scripts/a.py", "SKILL.md"])).toBe("SKILL.md");
    expect(defaultFile(["manifest.json"])).toBe("manifest.json");
    expect(NAME_RE.test("nasad-server2")).toBe(true);
    expect(NAME_RE.test("Nasad")).toBe(false);
    expect(NAME_RE.test("2x")).toBe(false);
  });
});
