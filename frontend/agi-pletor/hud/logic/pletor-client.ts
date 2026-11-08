import { api, apiStream } from "@/shared/types/logic/types";
import type { HeartStatus } from "@/layout/heart-channel/logic/heart-api";
import { statusLine } from "@/layout/heart-channel/logic/heart-status";
import { parseCswap, parseLlm, type CswapLlm, type PletorLlm } from "./llm-settings";

/** Síťová volání okna Pletor (docs/navrhy/2026-11-04-pletor-jarvis.md, P1) a mapování odpovědí na to, co okno ukáže. */

export type PletorRole = "human" | "pletor";
export type PletorMessage = { role: PletorRole; text: string; at: string };
export type PletorActionType = "heart_message" | "vault_note";
export type PletorAction = { type: PletorActionType; text: string; ok: boolean; detail?: string };
export type PletorReply = { reply: string; actions: PletorAction[] };
/** Zvolený mozek Pletora: Claude nebo Codex pod předplatným, nebo lokální model v Ollamě; přepíná se větou nebo v nastavení.
 *  `model` je model zvoleného mozku (Codex `null` = výchozí z Codexu), `available` modely Ollamy i při jiném mozku
 *  a `models` uložená volba modelu pro každý mozek (M2d). */
export type PletorBrainKind = "claude" | "codex" | "ollama";
export type PletorBrain = {
  brain: PletorBrainKind; model: string | null; available: string[];
  models: Record<PletorBrainKind, string | null>;
  /** Uložený effort Claude a Codexu, null = výchozí; Ollama effort nemá. */
  efforts: Record<"claude" | "codex", string | null>;
};
export type PletorState = { messages: PletorMessage[]; heart: unknown; escalations: unknown[]; brain: PletorBrain };

export const CLAUDE_BRAIN: PletorBrain = { brain: "claude", model: null, available: [], models: { claude: null, codex: null, ollama: null }, efforts: { claude: null, codex: null } };

/** Pole `brain` ze stavu; chybějící nebo cizí hodnota je Claude (výchozí mozek). */
export function parseBrain(value: unknown): PletorBrain {
  const raw = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
  const available = Array.isArray(raw.available) ? raw.available.filter((name): name is string => typeof name === "string") : [];
  const saved = (raw.models && typeof raw.models === "object" ? raw.models : {}) as Record<string, unknown>;
  const pick = (kind: PletorBrainKind) => (typeof saved[kind] === "string" && saved[kind] ? saved[kind] as string : null);
  const efforts = (raw.efforts && typeof raw.efforts === "object" ? raw.efforts : {}) as Record<string, unknown>;
  const level = (kind: "claude" | "codex") => (typeof efforts[kind] === "string" && efforts[kind] ? efforts[kind] as string : null);
  const known = raw.brain === "ollama" || raw.brain === "codex" || raw.brain === "claude";
  return {
    brain: known ? raw.brain as PletorBrainKind : "claude", available,
    model: known && typeof raw.model === "string" ? raw.model : null,
    models: { claude: pick("claude"), codex: pick("codex"), ollama: pick("ollama") },
    efforts: { claude: level("claude"), codex: level("codex") },
  };
}

/** Přepnutí mozku (`POST /api/pletor/brain {brain, model?, effort?}`; effort "" = výchozí); `ok: false` nese důvod v `reply` (např. Ollama nemá model). */
export const setPletorBrain = (brain: PletorBrainKind, model?: string, effort?: string) =>
  api<{ ok?: unknown; reply?: unknown; brain?: unknown }>("/api/pletor/brain", { brain, ...(model ? { model } : {}), ...(effort === undefined ? {} : { effort }) }).then((raw) => ({
    ok: raw.ok === true, reply: typeof raw.reply === "string" ? raw.reply : "", brain: parseBrain(raw.brain),
  }));

/** Readout mozku do rohu HUD: `claude · haiku`, `codex · gpt-6.1-sol`, `ollama · <model>`; bez modelu jen jméno mozku. */
export const brainText = (brain: PletorBrain) => (brain.model ? `${brain.brain} · ${brain.model}` : brain.brain);

const CLAUDE_NAMES: Record<string, string> = {
  fable: "Claude Fable 5.1", sonnet: "Claude Sonnet 5.5", opus: "Claude Opus 5.5", haiku: "Claude Haiku 5.5",
};

/** Co člověk vidí pod jádrem: který model mluví a kdo ho platí. Claude a Codex jedou pod předplatným, Ollama je lokální a zdarma. */
export function brainLabel(brain: PletorBrain): { name: string; plan: string; local: boolean } {
  if (brain.brain === "ollama") return { name: brain.model ?? "lokální model", plan: "lokální · zdarma", local: true };
  if (brain.brain === "codex") return { name: brain.model ?? "Codex", plan: "pod předplatným ChatGPT", local: false };
  const alias = brain.model ?? "sonnet";
  return { name: CLAUDE_NAMES[alias] ?? `Claude ${alias}`, plan: "cloud · předplatné", local: false };
}

const scope = (project: string, workspace: string) =>
  `project=${encodeURIComponent(project)}&workspace=${encodeURIComponent(workspace)}`;

/** Odpověď serveru → stav okna; chybějící nebo poškozená pole se čtou jako prázdná, neznámé role se zahodí. */
export function parseState(value: unknown): PletorState {
  const raw = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
  const messages = Array.isArray(raw.messages) ? raw.messages : [];
  return {
    messages: messages.filter((m): m is PletorMessage =>
      !!m && (m.role === "human" || m.role === "pletor") && typeof m.text === "string"),
    heart: raw.heart ?? null,
    escalations: Array.isArray(raw.escalations) ? raw.escalations : [],
    brain: parseBrain(raw.brain),
  };
}

export function parseReply(value: unknown): PletorReply {
  const raw = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
  const actions = Array.isArray(raw.actions) ? raw.actions : [];
  return {
    reply: typeof raw.reply === "string" ? raw.reply : "",
    actions: actions.filter((a): a is PletorAction => !!a && typeof a.type === "string" && typeof a.ok === "boolean"),
  };
}

/** Nastavení LLM na tomto počítači jen ke čtení (záložka LLM); vadná odpověď = sekce nedostupné s důvodem. */
export const fetchPletorLlm = (): Promise<PletorLlm> => api<unknown>("/api/pletor/llm").then(parseLlm);

/** Zápis modelu (M2): `PUT /api/pletor/llm/claude|codex`; vrací název zálohy (`null` = soubor dosud nebyl). */
/** Přepínač účtů: `cswap` = Claude Code (claude-swap), `codex` = Codex (codex-swap). */
export type AccountTool = "cswap" | "codex";
/** Spuštěné přihlášení: adresa k otevření, u Codexu i jednorázový kód, který člověk zadá na stránce. */
export type AccountLogin = { url: string; userCode: string | null };

export const startAccountLogin = (tool: AccountTool): Promise<AccountLogin> =>
  api<{ url?: unknown; userCode?: unknown }>(`/api/pletor/llm/${tool}/login`, {}).then((out) => {
    if (typeof out.url !== "string" || !out.url.startsWith("https://")) throw new Error("Server nevrátil adresu k přihlášení.");
    return { url: out.url, userCode: typeof out.userCode === "string" ? out.userCode : null };
  });
export const finishAccountLogin = (tool: AccountTool, code: string): Promise<CswapLlm> =>
  api<unknown>(`/api/pletor/llm/${tool}/login/code`, { code }).then(parseCswap);
export const cancelAccountLogin = (tool: AccountTool): Promise<unknown> => api<unknown>(`/api/pletor/llm/${tool}/login`, {}, "DELETE");
export const switchAccount = (tool: AccountTool, slot: number): Promise<CswapLlm> =>
  api<unknown>(`/api/pletor/llm/${tool}/switch`, { slot }).then(parseCswap);

export const putPletorLlm = (target: "claude" | "codex", body: { model: string; reasoning?: string; effort?: string }): Promise<string | null> =>
  api<{ backup?: unknown }>(`/api/pletor/llm/${target}`, body, "PUT").then((out) => (typeof out.backup === "string" ? out.backup : null));

export const fetchPletorState =(project: string, workspace: string) =>
  api<unknown>(`/api/pletor/state?${scope(project, workspace)}`).then(parseState);

/** `voice` (P3): zpráva vznikla hlasem nebo je zapnutý Hlas; server pak chce krátkou odpověď ke čtení nahlas. */
export const sendPletorMessage = (project: string, workspace: string, text: string, voice = false) =>
  api<unknown>("/api/pletor/messages", { project, workspace, text, ...(voice ? { voice } : {}) }).then(parseReply);

/** Hlasová zpráva proudem (`POST /api/pletor/messages/stream`, NDJSON): každý `delta` jde hned do `onDelta`, aby se
 *  odpověď četla po větách už při generování; výsledek je poslední řádek `done` (platí jeho `reply`). Proud bez `done` = selhání. */
export async function sendPletorMessageStream(project: string, workspace: string, text: string, voice: boolean,
  onDelta: (text: string) => void): Promise<PletorReply> {
  const reader = (await apiStream("/api/pletor/messages/stream", { project, workspace, text, ...(voice ? { voice } : {}) })).getReader();
  const decoder = new TextDecoder();
  let rest = "";
  for (;;) {
    const { done, value } = await reader.read();
    rest += decoder.decode(value, { stream: !done });
    const lines = rest.split("\n");
    rest = done ? "" : lines.pop()!; // nedokončený řádek počká na další kousek
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line) as { type?: unknown; text?: unknown };
      if (event.type === "delta" && typeof event.text === "string") onDelta(event.text);
      else if (event.type === "done") { void reader.cancel().catch(() => undefined); return parseReply(event); }
    }
    if (done) throw new Error("Pletor neodpověděl celý (proud skončil bez done).");
  }
}

/** Stav srdce jednou větou: řetězec ze serveru, nebo věta ze stavu srdce (`statusLine`), jinak přiznaná neznámá. */
export function heartText(heart: unknown): string {
  if (typeof heart === "string" && heart.trim()) return heart;
  if (heart && typeof heart === "object") {
    const value = heart as Record<string, unknown>;
    // Backend vrací jen {running, pending, sleeping, error, …}; chybějící pole srdce doplníme, jinak by `enabled` chybělo a řádek lhal.
    if (typeof value.running === "boolean") {
      const base = { enabled: true, pending: 0, batches: [], sleeping: false, sleepingUntil: null, nextAllowedAt: null, error: null };
      return statusLine({ ...base, ...value } as unknown as HeartStatus).text;
    }
    if (typeof value.state === "string") return value.state;
    if (typeof value.status === "string") return value.status;
  }
  return "Stav srdce neznámý";
}

export function escalationText(count: number): string {
  if (count === 0) return "žádná eskalace";
  if (count === 1) return "1 čekající eskalace";
  return count < 5 ? `${count} čekající eskalace` : `${count} čekajících eskalací`;
}

/** Provedená akce jako krátký štítek pro chip; selhání nese důvod. */
export function actionLabel(action: PletorAction): { ok: boolean; text: string } {
  if (!action.ok) return { ok: false, text: `Selhalo: ${action.detail || action.text || action.type}` };
  if (action.type === "heart_message") return { ok: true, text: "Poslal jsem srdci" };
  if (action.type === "vault_note") return { ok: true, text: "Zapsal do Schránky" };
  return { ok: true, text: action.text || action.type };
}

/** Režim Pletora drží App a neukládá ho: každý start OPORY začíná v kokpitu (HUD), jeden pro všechny projekty. */
export type PletorMode = "hud" | "window" | "closed";
