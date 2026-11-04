import { api } from "@/shared/types/logic/types";
import type { HeartStatus } from "@/layout/heart-channel/logic/heart-api";
import { statusLine } from "@/layout/heart-channel/logic/heart-status";

/** Síťová volání okna Pletor (docs/navrhy/2026-11-04-pletor-jarvis.md, P1) a mapování odpovědí na to, co okno ukáže. */

export type PletorRole = "human" | "pletor";
export type PletorMessage = { role: PletorRole; text: string; at: string };
export type PletorActionType = "heart_message" | "vault_note";
export type PletorAction = { type: PletorActionType; text: string; ok: boolean; detail?: string };
export type PletorReply = { reply: string; actions: PletorAction[] };
export type PletorState = { messages: PletorMessage[]; heart: unknown; escalations: unknown[] };

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

export const fetchPletorState = (project: string, workspace: string) =>
  api<unknown>(`/api/pletor/state?${scope(project, workspace)}`).then(parseState);

export const sendPletorMessage = (project: string, workspace: string, text: string) =>
  api<unknown>("/api/pletor/messages", { project, workspace, text }).then(parseReply);

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

/** Otevřenost okna je volba aplikace, ne projektu: jeden klíč pro všechny projekty. */
export const PLETOR_PREFS_KEY = "opora:pletor:v1";

export function readPletorOpen(): boolean {
  try {
    return JSON.parse(localStorage.getItem(PLETOR_PREFS_KEY) ?? "null")?.open === true;
  } catch {
    return false;
  }
}

export function writePletorOpen(open: boolean): void {
  try {
    localStorage.setItem(PLETOR_PREFS_KEY, JSON.stringify({ open }));
  } catch {
    /* Bez úložiště volba platí jen do zavření stránky. */
  }
}
