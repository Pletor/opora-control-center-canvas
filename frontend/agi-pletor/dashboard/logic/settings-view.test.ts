import { describe, expect, it } from "vitest";
import { parseLlm } from "@/agi-pletor/hud/logic/llm-settings";
import { modelProblem, savedNote, settingsView } from "./settings-view";

describe("settingsView", () => {
  it("mapuje modely, úroveň uvažování a MCP servery", () => {
    const view = settingsView(parseLlm({ claude: { available: true, model: "opus", mcp: ["a"] }, codex: { available: true, model: "gpt-6", reasoning: "high", mcp: ["b", "c"] } }));
    expect(view.claude).toMatchObject({ available: true, model: "opus" });
    expect(view.codex).toMatchObject({ model: "gpt-6", reasoning: "high", models: [] });
    expect(view.connectors).toEqual([{ source: "Claude Code", names: ["a"] }, { source: "Codex", names: ["b", "c"] }]);
  });
  it("nese modely do řádku; Claude má úrovně effortu", () => {
    const view = settingsView(parseLlm({ claude: { available: true, models: [{ id: "opus", label: "Opus" }] }, codex: { available: true, models: [{ id: "g", label: "G", reasoning: ["low"] }] } }));
    expect(view.claude.models).toEqual([{ id: "opus", label: "Opus", reasoning: ["low", "medium", "high", "xhigh", "max"] }]);
    expect(view.codex.models).toEqual([{ id: "g", label: "G", reasoning: ["low"] }]);
  });

  it("nedostupná sekce nese důvod, uvažování z cache se nezahazuje, bez dat je vše prázdné", () => {
    const view = settingsView(parseLlm({ claude: { available: false, reason: "chybí" }, codex: { available: true, reasoning: "xhigh" } }));
    expect(view.claude).toMatchObject({ available: false, reason: "chybí" });
    expect(view.codex.reasoning).toBe("xhigh");
    expect(settingsView(null).claude.available).toBe(false);
  });
});

describe("modelProblem / savedNote", () => {
  it("validuje jako server", () => {
    expect(modelProblem("claude-opus-4.5:x_1")).toBeNull();
    for (const bad of ["", "a b", "x".repeat(101), 'a"b']) expect(modelProblem(bad)).not.toBeNull();
  });
  it("potvrzení se zálohou i bez", () => {
    expect(savedNote("settings.json.bak-1")).toBe("uloženo, záloha settings.json.bak-1");
    expect(savedNote(null)).toContain("bez zálohy");
  });
});
