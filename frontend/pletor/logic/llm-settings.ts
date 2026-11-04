/** Záložka LLM v nastavení Pletora (docs/navrhy/2026-11-04-pletor-nastaveni-llm.md, M1): tvar `GET /api/pletor/llm`
 *  a jeho odolné čtení. Každá sekce nese `available` a u nedostupné `reason`; chybějící pole jsou prázdná. */

type Base = { available: boolean; reason: string | null };
export type ClaudeLlm = Base & {
  version: string | null; model: string | null; hooks: number; mcp: string[]; permissionsMode: string | null;
  loggedIn: boolean; claudeMd: boolean; skills: number;
};
export type CodexLlm = Base & {
  version: string | null; model: string | null; reasoning: string | null; approval: string | null; sandbox: string | null;
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
export type CswapLlm = Base & { installHint: string | null; accounts: CswapAccount[] };
export type PletorLlm = { claude: ClaudeLlm; codex: CodexLlm; ollama: OllamaLlm; cswap: CswapLlm };

type Raw = Record<string, unknown>;
const obj = (value: unknown): Raw => (value && typeof value === "object" && !Array.isArray(value) ? value as Raw : {});
const str = (value: unknown) => (typeof value === "string" && value ? value : null);
const num = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : null);
const strings = (value: unknown) => (Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []);
const list = (value: unknown) => (Array.isArray(value) ? value.map(obj) : []);

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
      ...base(claude), version: str(claude.version), model: str(claude.model), hooks: num(claude.hooks) ?? 0, mcp: strings(claude.mcp),
      permissionsMode: str(claude.permissionsMode), loggedIn: claude.loggedIn === true, claudeMd: claude.claudeMd === true, skills: num(claude.skills) ?? 0,
    },
    codex: {
      ...base(codex), version: str(codex.version), model: str(codex.model), reasoning: str(codex.reasoning), approval: str(codex.approval),
      sandbox: str(codex.sandbox), mcp: strings(codex.mcp), loggedIn: codex.loggedIn === true,
    },
    ollama: {
      ...base(ollama),
      installed: list(ollama.installed).filter((m) => str(m.name)).map((m) => ({ name: String(m.name), sizeGb: num(m.sizeGb) ?? 0 })),
      loaded: list(ollama.loaded).filter((m) => str(m.name)).map((m) => ({ name: String(m.name), vramGb: num(m.vramGb) ?? 0 })),
      vram: num(vram.totalGb) === null ? null : { totalGb: num(vram.totalGb)!, usedGb: num(vram.usedGb) ?? 0, freeGb: num(vram.freeGb) ?? 0 },
    },
    cswap: {
      ...base(cswap), installHint: str(cswap.installHint),
      accounts: list(cswap.accounts).map((a) => ({
        slot: num(a.slot), label: str(a.label) ?? "?", alias: str(a.alias), active: a.active === true,
        usage5h: num(a.usage5h), usage7d: num(a.usage7d), resetsAt: str(a.resetsAt),
      })),
    },
  };
}

/** Barva pruhu využití jako v HUD: do 70 % zelená, do 90 % jantarová, výš červená; neznámé tlumené. */
export function usageTone(pct: number | null): "ok" | "warn" | "high" | "unknown" {
  if (pct === null) return "unknown";
  return pct < 70 ? "ok" : pct < 90 ? "warn" : "high";
}
