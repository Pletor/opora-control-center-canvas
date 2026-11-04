import { api, apiStream } from "@/shared/types/logic/types";
import type { HeartStatus } from "@/layout/heart-channel/logic/heart-api";
import { statusLine } from "@/layout/heart-channel/logic/heart-status";
import { parseLlm, type PletorLlm } from "./llm-settings";

/** Síťová volání okna Pletor (docs/navrhy/2026-11-04-pletor-jarvis.md, P1) a mapování odpovědí na to, co okno ukáže. */

export type PletorRole = "human" | "pletor";
export type PletorMessage = { role: PletorRole; text: string; at: string };
export type PletorActionType = "heart_message" | "vault_note";
export type PletorAction = { type: PletorActionType; text: string; ok: boolean; detail?: string };
export type PletorReply = { reply: string; actions: PletorAction[] };
/** Zvolený mozek Pletora (P2): Claude pod předplatným, nebo lokální model v Ollamě; přepíná se větou nebo v nastavení.
 *  `available` jsou modely Ollamy i při Claude, aby nastavení ukázalo, kterým lokálním modelem by Pletor mluvil. */
export type PletorBrain = { brain: "claude" | "ollama"; model: string | null; available: string[] };
export type PletorState = { messages: PletorMessage[]; heart: unknown; escalations: unknown[]; brain: PletorBrain };

export const CLAUDE_BRAIN: PletorBrain = { brain: "claude", model: null, available: [] };

/** Pole `brain` ze stavu; chybějící nebo cizí hodnota je Claude (výchozí mozek). */
export function parseBrain(value: unknown): PletorBrain {
  const raw = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
  const available = Array.isArray(raw.available) ? raw.available.filter((name): name is string => typeof name === "string") : [];
  const model = typeof raw.model === "string" ? raw.model : null;
  return { brain: raw.brain === "ollama" ? "ollama" : "claude", model: raw.brain === "ollama" || raw.brain === "claude" ? model : null, available };
}

/** Přepnutí mozku (`POST /api/pletor/brain`); `ok: false` nese důvod v `reply` (např. Ollama nemá model). */
export const setPletorBrain = (brain: PletorBrain["brain"]) =>
  api<{ ok?: unknown; reply?: unknown; brain?: unknown }>("/api/pletor/brain", { brain }).then((raw) => ({
    ok: raw.ok === true, reply: typeof raw.reply === "string" ? raw.reply : "", brain: parseBrain(raw.brain),
  }));

/** Readout mozku do rohu HUD: `claude`, nebo `ollama · <model>`. */
export const brainText = (brain: PletorBrain) => (brain.brain === "ollama" && brain.model ? `ollama · ${brain.model}` : brain.brain);

const CLAUDE_NAMES: Record<string, string> = { sonnet: "Claude Sonnet 5.5", opus: "Claude Opus 5.5", haiku: "Claude Haiku 5.5" };

/** Co člověk vidí pod jádrem: který model mluví a kdo ho platí. Claude jede pod předplatným, Ollama je lokální a zdarma. */
export function brainLabel(brain: PletorBrain): { name: string; plan: string; local: boolean } {
  if (brain.brain === "ollama") return { name: brain.model ?? "lokální model", plan: "lokální · zdarma", local: true };
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

export const fetchPletorState = (project: string, workspace: string) =>
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
