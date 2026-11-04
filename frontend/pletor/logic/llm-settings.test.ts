import { describe, expect, it } from "vitest";
import { parseLlm, usageTone } from "./llm-settings";

describe("nastavení LLM", () => {
  it("prázdná nebo cizí odpověď = čtyři nedostupné sekce s důvodem", () => {
    const llm = parseLlm(null);
    expect(llm.claude).toMatchObject({ available: false, reason: "Server sekci nevrátil.", mcp: [], hooks: 0 });
    expect(llm.ollama).toMatchObject({ available: false, installed: [], loaded: [], vram: null });
    expect(llm.cswap).toMatchObject({ available: false, installHint: null, accounts: [] });
  });

  it("přečte sekce a zahodí vadné položky", () => {
    const llm = parseLlm({
      claude: { available: true, model: "opus", hooks: 3, mcp: ["a", 1], loggedIn: true, skills: 4 },
      ollama: { available: true, installed: [{ name: "qwen3:14b", sizeGb: 9 }, { size: 1 }], loaded: [{ name: "qwen3:14b", vramGb: 10.5 }],
        vram: { totalGb: 12, usedGb: 8.8, freeGb: 3.2 } },
      cswap: { available: false, reason: "chybí", installHint: "uv tool install claude-swap" },
      codex: { available: true, reasoning: "high", loggedIn: "yes" },
    });
    expect(llm.claude).toMatchObject({ available: true, reason: null, model: "opus", hooks: 3, mcp: ["a"], loggedIn: true, skills: 4, version: null });
    expect(llm.ollama.installed).toEqual([{ name: "qwen3:14b", sizeGb: 9 }]);
    expect(llm.ollama.vram).toEqual({ totalGb: 12, usedGb: 8.8, freeGb: 3.2 });
    expect(llm.cswap).toMatchObject({ available: false, reason: "chybí", installHint: "uv tool install claude-swap" });
    expect(llm.codex).toMatchObject({ reasoning: "high", loggedIn: false });
  });

  it("účty cswap s využitím, neznámé využití je null", () => {
    const { accounts } = parseLlm({ cswap: { available: true, accounts: [
      { slot: 1, label: "j***@d***.cz", active: true, usage5h: 42, usage7d: 91.5, resetsAt: "2026-11-04T18:00:00Z" },
      { slot: 2, label: "e***@f***.uk", alias: "práce", usage5h: null },
    ] } }).cswap;
    expect(accounts).toEqual([
      { slot: 1, label: "j***@d***.cz", alias: null, active: true, usage5h: 42, usage7d: 91.5, resetsAt: "2026-11-04T18:00:00Z" },
      { slot: 2, label: "e***@f***.uk", alias: "práce", active: false, usage5h: null, usage7d: null, resetsAt: null },
    ]);
  });

  it("barva pruhu: zelená → jantarová → červená", () => {
    expect([usageTone(0), usageTone(69.9), usageTone(70), usageTone(89), usageTone(90), usageTone(null)]).toEqual(["ok", "ok", "warn", "warn", "high", "unknown"]);
  });
});
