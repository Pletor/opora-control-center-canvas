import { CLAUDE_EFFORTS, type CodexModel, type PletorLlm } from "@/agi-pletor/hud/logic/llm-settings";

/** Nastavení velínu (V4): pohled na modely Claude Code a Codexu, jejich effort a na názvy MCP serverů. */

/** Stejné pravidlo jako server (`llm_settings/write.py`): 1–100 znaků z písmen, číslic a `- . _ :`. */
export const MODEL_PATTERN = /^[A-Za-z0-9._:-]{1,100}$/;
export const modelProblem = (model: string): string | null =>
  MODEL_PATTERN.test(model) ? null : "Model: 1–100 znaků z písmen, číslic a - . _ :";

/** Potvrzení po uložení; bez zálohy (soubor dosud neexistoval) to říká výslovně. */
export const savedNote = (backup: string | null): string =>
  backup ? `uloženo, záloha ${backup}` : "uloženo, soubor dosud neexistoval, bez zálohy";

export type ModelRow = { available: boolean; reason: string; model: string; models: CodexModel[]; reasoning: string | null };
export type SettingsView = {
  claude: ModelRow;
  codex: ModelRow;
  connectors: { source: string; names: string[] }[];
};

export function settingsView(llm: PletorLlm | null): SettingsView {
  const claude = llm?.claude, codex = llm?.codex;
  return {
    claude: { available: claude?.available === true, reason: claude?.reason ?? "", model: claude?.model ?? "", models: (claude?.models ?? []).map((m) => ({ ...m, reasoning: CLAUDE_EFFORTS })), reasoning: claude?.effort ?? null },
    codex: { available: codex?.available === true, reason: codex?.reason ?? "", model: codex?.model ?? "", models: codex?.models ?? [], reasoning: codex?.reasoning ?? null },
    connectors: [
      { source: "Claude Code", names: claude?.mcp ?? [] },
      { source: "Codex", names: codex?.mcp ?? [] },
    ],
  };
}
