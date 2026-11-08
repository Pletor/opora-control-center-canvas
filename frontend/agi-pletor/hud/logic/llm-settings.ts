/** Záložka LLM v nastavení Pletora (docs/navrhy/2026-11-04-pletor-nastaveni-llm.md, M1): tvar `GET /api/pletor/llm`
 *  a jeho odolné čtení. Každá sekce nese `available` a u nedostupné `reason`; chybějící pole jsou prázdná. */

/** Úrovně effortu Claude Code (`llm_settings.claude.EFFORTS`) a výchozí úrovně Codexu, když cache modelu žádné nenese. */
export const CLAUDE_EFFORTS = ["low", "medium", "high", "xhigh", "max"];
export const CODEX_EFFORTS = ["low", "medium", "high"];

type Base = { available: boolean; reason: string | null };
/** Model k výběru; `reasoning` (jen Codex) jsou úrovně uvažování, které model umí. */
export type LlmModel = { id: string; label: string };
export type CodexModel = LlmModel & { reasoning: string[] };
export type ClaudeLlm = Base & {
  models: LlmModel[]; version: string | null; model: string | null; effort: string | null; hooks: number; mcp: string[]; permissionsMode: string | null;
  loggedIn: boolean; claudeMd: boolean; skills: number;
};
export type CodexLlm = Base & {
  models: CodexModel[]; version: string | null; model: string | null; reasoning: string | null; approval: string | null; sandbox: string | null;
  mcp: string[]; loggedIn: boolean;
};
export type OllamaLlm = Base & {
  installed: { name: string; sizeGb: number }[]; loaded: { name: string; vramGb: number }[];
  vram: { totalGb: number; usedGb: number; freeGb: number } | null;
};
export type CswapAccount = {
  slot: number | null; label: string; alias: string | null; active: boolean;
  usage5h: number | null; usage7d: number | null; resetsAt: string | null;
};
/** `managed` false = Claude Code je přihlášený účtem mimo uložené (UI nabídne Uložit). */
export type CswapLlm = Base & { installHint: string | null; managed: boolean; accounts: CswapAccount[] };
/** `codexswap` = účty Codexu přes codex-swap, stejný tvar jako `cswap`. */
export type PletorLlm = { claude: ClaudeLlm; codex: CodexLlm; ollama: OllamaLlm; cswap: CswapLlm; codexswap: CswapLlm };

type Raw = Record<string, unknown>;
const obj = (value: unknown): Raw => (value && typeof value === "object" && !Array.isArray(value) ? value as Raw : {});
const str = (value: unknown) => (typeof value === "string" && value ? value : null);
const num = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : null);
const strings = (value: unknown) => (Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []);
const list = (value: unknown) => (Array.isArray(value) ? value.map(obj) : []);

/** Položky bez `id` se zahodí; chybějící `label` = id; `reasoning` jen řetězce. */
function models(value: unknown): CodexModel[] {
  return list(value).filter((m) => str(m.id)).map((m) => ({ id: String(m.id), label: str(m.label) ?? String(m.id), reasoning: strings(m.reasoning) }));
}

function base(raw: Raw): Base {
  const available = raw.available === true;
  return { available, reason: available ? null : str(raw.reason) ?? "Server sekci nevrátil." };
}

export function parseLlm(value: unknown): PletorLlm {
  const root = obj(value);
  const claude = obj(root.claude), codex = obj(root.codex), ollama = obj(root.ollama), cswap = obj(root.cswap);
  const vram = obj(ollama.vram);
  return {
    claude: {
      ...base(claude), models: models(claude.models).map(({ id, label }) => ({ id, label })), version: str(claude.version), model: str(claude.model), effort: str(claude.effort), hooks: num(claude.hooks) ?? 0, mcp: strings(claude.mcp),
      permissionsMode: str(claude.permissionsMode), loggedIn: claude.loggedIn === true, claudeMd: claude.claudeMd === true, skills: num(claude.skills) ?? 0,
    },
    codex: {
      ...base(codex), models: models(codex.models), version: str(codex.version), model: str(codex.model), reasoning: str(codex.reasoning), approval: str(codex.approval),
      sandbox: str(codex.sandbox), mcp: strings(codex.mcp), loggedIn: codex.loggedIn === true,
    },
    ollama: {
      ...base(ollama),
      installed: list(ollama.installed).filter((m) => str(m.name)).map((m) => ({ name: String(m.name), sizeGb: num(m.sizeGb) ?? 0 })),
      loaded: list(ollama.loaded).filter((m) => str(m.name)).map((m) => ({ name: String(m.name), vramGb: num(m.vramGb) ?? 0 })),
      vram: num(vram.totalGb) === null ? null : { totalGb: num(vram.totalGb)!, usedGb: num(vram.usedGb) ?? 0, freeGb: num(vram.freeGb) ?? 0 },
    },
    cswap: parseCswap(cswap),
    codexswap: parseCswap(root.codexswap),
  };
}

/** Sekce účtů (`GET /llm` i odpovědi `POST /llm/cswap/*`). */
export function parseCswap(value: unknown): CswapLlm {
  const cswap = obj(value);
  return {
    ...base(cswap), installHint: str(cswap.installHint), managed: cswap.managed !== false,
    accounts: list(cswap.accounts).map((a) => ({
      slot: num(a.slot), label: str(a.label) ?? "?", alias: str(a.alias), active: a.active === true,
      usage5h: num(a.usage5h), usage7d: num(a.usage7d), resetsAt: str(a.resetsAt),
    })),
  };
}

/** Úrovně effortu modelu Codexu z cache; model bez nich = `CODEX_EFFORTS`. */
export const codexEfforts = (models: (LlmModel & { reasoning?: string[] })[], id: string | null): string[] => {
  const found = models.find((m) => m.id === id)?.reasoning ?? [];
  return found.length ? found : CODEX_EFFORTS;
};

/** Při změně modelu zůstane dosavadní effort jen tehdy, když ho nový model umí; jinak „výchozí“ (""). */
export const keepEffort = (levels: string[], current: string | null): string => (current && levels.includes(current) ? current : "");

/** Barva pruhu využití jako v HUD: do 70 % zelená, do 90 % jantarová, výš červená; neznámé tlumené. */
export function usageTone(pct: number | null): "ok" | "warn" | "high" | "unknown" {
  if (pct === null) return "unknown";
  return pct < 70 ? "ok" : pct < 90 ? "warn" : "high";
}
