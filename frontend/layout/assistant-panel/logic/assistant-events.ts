/**
 * Čistý reducer konverzace asistenta: události SSE a přepis historie se skládají do jednoho stavu.
 * Žádný React, žádné síťové volání. Jeden tah vypadá takto: `text_delta` průběžně roste zpráva,
 * `message` se stejným `messageId` ji nahradí finálním textem (nevznikne duplicita), `tool_use`
 * otevře řádek nástroje a `tool_result` se stejným `id` ho uzavře.
 */

export type SessionState = "idle" | "running" | "waiting_approval" | "closed" | "error";

export type AssistantEvent = { seq?: number; type: string; [key: string]: unknown };

type MessageItem = { kind: "message"; id: string; role: "user" | "assistant"; text: string; streaming: boolean; origin: "history" | "live" | "local" };

export type ChatItem =
  | MessageItem
  | { kind: "tool"; id: string; name: string; summary: string; status: "running" | "ok" | "error"; result: string }
  | { kind: "error"; id: string; text: string };

export type TurnInfo = { durationMs: number; isError: boolean; numTurns: number; denied: number };

export type Conversation = {
  items: ChatItem[];
  /** Nejvyšší zpracovaný seq; události s nižším nebo stejným seq se ignorují. */
  lastSeq: number;
  state: SessionState;
  lastTurn: TurnInfo | null;
};

export const STATES: SessionState[] = ["idle", "running", "waiting_approval", "closed", "error"];

export function emptyConversation(state: SessionState = "idle", lastSeq = 0): Conversation {
  return { items: [], lastSeq, state, lastTurn: null };
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** Přepis z `GET …/transcript` je historie; události pak navazují od `lastSeq`. */
export function loadTranscript(
  messages: { role: string; text: string }[],
  state: SessionState = "idle",
  lastSeq = 0,
): Conversation {
  const items: ChatItem[] = [];
  messages.forEach((m, i) => {
    if (m.role !== "user" && m.role !== "assistant") return;
    items.push({ kind: "message", id: `h${i}`, role: m.role, text: m.text, streaming: false, origin: "history" });
  });
  return { items, lastSeq, state, lastTurn: null };
}

/** Zpráva, kterou uživatel právě odeslal: ukáže se hned, server ji později jen potvrdí. */
export function addLocalUserMessage(conv: Conversation, text: string, id: string): Conversation {
  return {
    ...conv,
    state: "running",
    items: [...conv.items, { kind: "message", id, role: "user", text, streaming: false, origin: "local" }],
  };
}

/** Odeslání se nepovedlo: místní zpráva se vrátí a chyba se ukáže jako červený řádek. */
export function failLocalMessage(conv: Conversation, id: string, text: string, state: SessionState = "idle"): Conversation {
  return {
    ...conv,
    state,
    items: [...conv.items.filter((it) => it.id !== id), { kind: "error", id: `e-${id}`, text }],
  };
}

function finishStreaming(items: ChatItem[]): ChatItem[] {
  return items.map((it) => (it.kind === "message" && it.streaming ? { ...it, streaming: false } : it));
}

function onMessage(conv: Conversation, event: AssistantEvent, seq: number): Conversation {
  const role = event.role === "user" ? "user" : "assistant";
  const text = str(event.text);
  const messageId = str(event.messageId);
  const items = conv.items;
  if (messageId) {
    const index = items.findIndex((it) => it.kind === "message" && it.id === messageId);
    if (index >= 0) {
      const next = items.slice();
      next[index] = { kind: "message", id: messageId, role, text, streaming: false, origin: "live" };
      return { ...conv, items: next };
    }
  }
  if (role === "user") {
    // Odeslaná zpráva čeká jako místní; server ji potvrdí, nepřidá se podruhé.
    const local = items.findIndex((it) => it.kind === "message" && it.origin === "local" && it.role === "user" && it.text === text);
    if (local >= 0) {
      const next = items.slice();
      next[local] = { ...(next[local] as MessageItem), origin: "live" };
      return { ...conv, items: next };
    }
  }
  // Zpráva, která už je v přepisu (výpadek mezi seznamem a přepisem), se nezdvojí.
  const last = items[items.length - 1];
  if (last && last.kind === "message" && last.origin === "history" && last.role === role && last.text === text) return conv;
  return {
    ...conv,
    items: [...items, { kind: "message", id: messageId || `m${seq}`, role, text, streaming: false, origin: "live" }],
  };
}

function onTextDelta(conv: Conversation, event: AssistantEvent, seq: number): Conversation {
  const id = str(event.messageId) || `m${seq}`;
  const text = str(event.text);
  const index = conv.items.findIndex((it) => it.kind === "message" && it.id === id);
  if (index >= 0) {
    const item = conv.items[index] as MessageItem;
    const next = conv.items.slice();
    next[index] = { ...item, text: item.text + text, streaming: true };
    return { ...conv, items: next };
  }
  return { ...conv, items: [...conv.items, { kind: "message", id, role: "assistant", text, streaming: true, origin: "live" }] };
}

function onToolResult(conv: Conversation, event: AssistantEvent, seq: number): Conversation {
  const id = str(event.id);
  const status = event.ok === false ? "error" : "ok";
  const result = str(event.summary);
  const index = conv.items.findIndex((it) => it.kind === "tool" && it.id === id);
  if (index < 0) {
    const row: ChatItem = { kind: "tool", id: id || `t${seq}`, name: "nástroj", summary: "", status, result };
    return { ...conv, items: [...conv.items, row] };
  }
  const item = conv.items[index] as Extract<ChatItem, { kind: "tool" }>;
  const next = conv.items.slice();
  next[index] = { ...item, status, result };
  return { ...conv, items: next };
}

/** Jedna událost SSE do stavu. Neznámé typy a už viděné `seq` stav nemění. */
export function applyEvent(conv: Conversation, event: AssistantEvent): Conversation {
  const seq = typeof event.seq === "number" ? event.seq : null;
  if (seq !== null && seq <= conv.lastSeq) return conv;
  const base = seq !== null ? { ...conv, lastSeq: seq } : conv;
  const at = seq ?? base.lastSeq;
  switch (event.type) {
    case "status": {
      const state = STATES.find((s) => s === event.state);
      return state ? { ...base, state } : base;
    }
    case "text_delta":
      return onTextDelta(base, event, at);
    case "message":
      return onMessage(base, event, at);
    case "tool_use": {
      const id = str(event.id) || `t${at}`;
      if (base.items.some((it) => it.kind === "tool" && it.id === id)) return base;
      const row: ChatItem = { kind: "tool", id, name: str(event.name) || "nástroj", summary: str(event.summary), status: "running", result: "" };
      return { ...base, items: [...base.items, row] };
    }
    case "tool_result":
      return onToolResult(base, event, at);
    case "turn_end": {
      const denied = Array.isArray(event.denied) ? event.denied.length : typeof event.denied === "number" ? event.denied : 0;
      const lastTurn: TurnInfo = {
        durationMs: typeof event.durationMs === "number" ? event.durationMs : 0,
        isError: event.isError === true,
        numTurns: typeof event.numTurns === "number" ? event.numTurns : 0,
        denied,
      };
      return { ...base, items: finishStreaming(base.items), lastTurn, state: base.state === "error" ? "error" : "idle" };
    }
    case "error":
      return {
        ...base,
        items: [...finishStreaming(base.items), { kind: "error", id: `e${at}`, text: str(event.message) || "Neznámá chyba asistenta." }],
        state: "error",
      };
    default:
      return base;
  }
}

/** Běží-li tah (nebo čeká na schválení), další zpráva se odeslat nedá. */
export function isBusy(state: SessionState): boolean {
  return state === "running" || state === "waiting_approval";
}
