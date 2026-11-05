import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchSkillFile, fetchSkills, fetchTool, measureTool, parseGenerated, parseMeasure, parseSkills, parseTools, saveSkillFile, saveTool } from "./workshop-api";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(body: unknown) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return { ok: true, status: 200, text: async () => JSON.stringify(body), headers: { get: () => null } };
  });
  return calls;
}
const writes = (calls: { url: string; init?: RequestInit }[]) => calls.filter((c) => c.url.startsWith("/api/pletor/workshop"));

describe("čtení odpovědí Dílny", () => {
  it("chybějící pole jsou prázdná, položky bez jména pryč", () => {
    expect(parseSkills({ skills: [{ name: "deploy", files: ["SKILL.md", 3] }, { description: "bez jména" }] }))
      .toEqual([{ name: "deploy", description: "", files: ["SKILL.md"] }]);
    expect(parseSkills(null)).toEqual([]);
    expect(parseTools({ tools: [{ name: "sum" }, "x"] })).toEqual([{ name: "sum", path: "", cases: 0 }]);
  });

  it("měření: selhání s got/expected, prázdná chyba je null, chybějící determinismus je ne", () => {
    expect(parseMeasure({ name: "sum", passed: 1, total: 2, failed: [{ name: "a", got: 3, expected: { x: 1 } }], durationMs: 4.2, error: "" }))
      .toEqual({ name: "sum", passed: 1, total: 2, failed: [{ name: "a", got: 3, expected: { x: 1 } }], durationMs: 4.2, deterministic: false, error: null });
  });
});

describe("volání Dílny", () => {
  it("čte seznam a soubor skillu s kódovanou cestou", async () => {
    let calls = stubFetch({ skills: [{ name: "deploy", description: "d", files: ["SKILL.md"] }] });
    expect(await fetchSkills()).toHaveLength(1);
    expect(calls[0].url).toBe("/api/pletor/workshop/skills");
    calls = stubFetch({ path: "scripts/a b.py", content: "print(1)" });
    expect(await fetchSkillFile("deploy", "scripts/a b.py")).toBe("print(1)");
    expect(calls[0].url).toBe("/api/pletor/workshop/skills/deploy/file?path=scripts%2Fa%20b.py");
  });

  it("ukládá soubor skillu a funkci metodou PUT s JSON tělem", async () => {
    const calls = stubFetch({ path: "SKILL.md", bytes: 3 });
    await saveSkillFile("deploy", "SKILL.md", "abc");
    await saveTool("sum", "def run(v): return v", "[]");
    const [skill, tool] = writes(calls);
    expect(skill.init?.method).toBe("PUT");
    expect(JSON.parse(String(skill.init!.body))).toEqual({ path: "SKILL.md", content: "abc" });
    expect(tool.url).toBe("/api/pletor/workshop/tools/sum");
    expect(JSON.parse(String(tool.init!.body))).toEqual({ code: "def run(v): return v", cases: "[]" });
  });

  it("načte funkci a změří ji POSTem s prázdným tělem", async () => {
    let calls = stubFetch({ name: "sum", code: "x", cases: "[1]" });
    expect(await fetchTool("sum")).toEqual({ name: "sum", code: "x", cases: "[1]" });
    calls = stubFetch({ name: "sum", passed: 2, total: 2, failed: [], durationMs: 3, deterministic: true });
    expect(await measureTool("sum")).toMatchObject({ passed: 2, deterministic: true, error: null });
    const [measure] = writes(calls);
    expect(measure.url).toBe("/api/pletor/workshop/tools/sum/measure");
    expect(measure.init?.method).toBe("POST");
    expect(JSON.parse(String(measure.init!.body))).toEqual({});
  });
});

describe("parseGenerated", () => {
  it("případy jdou do editoru jako formátovaný JSON a měření se přečte", () => {
    const cases = [{ name: "c", input: {}, expected: {} }];
    const done = parseGenerated({ name: "a", code: "x", cases, measure: { name: "a", passed: 1, total: 1 } });
    expect(done.source.cases).toBe(`${JSON.stringify(cases, null, 2)}\n`);
    expect(done.measure.passed).toBe(1);
    expect(parseGenerated(null).source.cases).toBe("[]\n");
  });
});
