// Vazba konverzace aktivní session na React a síť. Konverzaci skládá čistý reducer z
// assistant-events.ts: nejdřív přepis (historie), pak EventSource od `lastSeq` (jen nové události,
// už viděné `seq` reducer zahodí). Přepnutí session starý EventSource zavře. Volá ho jen AssistantPanel.
// Úkol, který čeká na schválení, se otevře s přehráním bufferu od začátku: reducer z něj vezme jen
// čekající žádosti o zápis, aby karta schválení byla vidět i po přepnutí úkolu.
// Vedle reduceru běží hlídač zápisu (canvas-write.ts): povolený zápis, který doběhl, ohlásí
// `onCanvasWritten` (docs/asistent.md §6.2); přehrané staré události ho nespustí.
import { useCallback, useEffect, useRef, useState } from "react";
import { markPending, markSending, resolveApproval, updateApproval } from "./approval";
import { decideApproval, eventsUrl, fetchSessions, fetchTranscript, sendMessage, stopSession, type AssistantContext } from "./assistant-api";
import {
  addLocalUserMessage,
  applyEvent,
  emptyConversation,
  failLocalMessage,
  loadTranscript,
  type AssistantEvent,
  type Conversation,
} from "./assistant-events";
import { startWatch, watchEvent } from "./canvas-write";
import { messageOf } from "./use-assistant-sessions";

const EVENT_TYPES = ["status", "text_delta", "message", "tool_use", "tool_result", "progress", "turn_end", "error", "approval", "approval_resolved"];

const EMPTY = emptyConversation();

export type ConversationApi = {
  conv: Conversation;
  loading: boolean;
  send: (text: string, context: AssistantContext) => Promise<boolean>;
  stop: () => Promise<void>;
  decide: (approvalId: string, decision: "allow" | "deny", note?: string) => Promise<void>;
};

export function useConversation(
  enabled: boolean,
  project: string,
  activeId: string | null,
  onFailure: (text: string) => void,
  onCanvasWritten: () => void = () => {},
): ConversationApi {
  // Konverzace nese id své session: po přepnutí úkolu se do nového nikdy nedostane obsah starého
  // (ani na jeden render, ani pozdní událostí z dobíhajícího streamu).
  const [owned, setOwned] = useState<{ id: string | null; conv: Conversation }>({ id: null, conv: emptyConversation() });
  const update = useCallback((id: string, change: (c: Conversation) => Conversation) => {
    setOwned((o) => (o.id === id ? { id, conv: change(o.conv) } : o));
  }, []);
  const [loading, setLoading] = useState(false);
  const counter = useRef(0);
  const failure = useRef(onFailure);
  failure.current = onFailure;
  const written = useRef(onCanvasWritten);
  written.current = onCanvasWritten;

  // Historie z přepisu, potom jen nové události; cleanup zavře EventSource staré session.
  useEffect(() => {
    setOwned({ id: activeId, conv: emptyConversation() });
    if (!enabled || !activeId || !project) return;
    let alive = true;
    let source: EventSource | null = null;
    setLoading(true);
    (async () => {
      const list = await fetchSessions(project);
      const meta = list.find((s) => s.id === activeId);
      const messages = await fetchTranscript(activeId);
      if (!alive) return;
      update(activeId, () => loadTranscript(messages, meta?.state ?? "idle", meta?.lastSeq ?? 0));
      setLoading(false);
      const after = meta?.state === "waiting_approval" ? 0 : meta?.lastSeq ?? 0;
      let watch = startWatch(meta?.lastSeq ?? 0);
      const opened = new EventSource(eventsUrl(activeId, after));
      source = opened;
      const handle = (message: MessageEvent) => {
        try {
          const event = JSON.parse(message.data) as AssistantEvent;
          if (!event || typeof event.type !== "string") return;
          update(activeId, (c) => applyEvent(c, event));
          const watched = watchEvent(watch, event);
          watch = watched.watch;
          if (watched.written) written.current();
        } catch { /* Poškozený řádek streamu se přeskočí. */ }
      };
      opened.onmessage = handle;
      EVENT_TYPES.forEach((type) => opened.addEventListener(type, handle as EventListener));
    })().catch((e) => {
      if (!alive) return;
      setLoading(false);
      failure.current(messageOf(e));
    });
    return () => { alive = false; source?.close(); };
  }, [enabled, activeId, project, update]);

  const send = useCallback(async (text: string, context: AssistantContext) => {
    if (!activeId) return false;
    const localId = `local-${++counter.current}`;
    update(activeId, (c) => addLocalUserMessage(c, text, localId, Date.now()));
    try {
      await sendMessage(activeId, text, context);
      return true;
    } catch (e) {
      // Backend vrací české důvody (běžící tah, limit procesů, neplatný kontext); ukážou se beze změny.
      update(activeId, (c) => failLocalMessage(c, localId, messageOf(e), "idle"));
      return false;
    }
  }, [activeId, update]);

  const stop = useCallback(async () => {
    if (!activeId) return;
    try {
      await stopSession(activeId);
      update(activeId, (c) => ({ ...c, state: "idle" }));
    } catch (e) { failure.current(messageOf(e)); }
  }, [activeId, update]);

  // Rozhodnutí se ukáže hned; `approval_resolved` ze serveru pak kartu jen potvrdí. Chyba vrátí kartu.
  const decide = useCallback(async (approvalId: string, decision: "allow" | "deny", note?: string) => {
    if (!activeId) return;
    update(activeId, (c) => updateApproval(c, approvalId, markSending));
    try {
      await decideApproval(approvalId, decision, note);
      update(activeId, (c) => updateApproval(c, approvalId, (a) => resolveApproval(a, { decision, note })));
    } catch (e) {
      update(activeId, (c) => updateApproval(c, approvalId, markPending));
      failure.current(messageOf(e));
    }
  }, [activeId, update]);

  const conv = owned.id === activeId ? owned.conv : EMPTY;
  return { conv, loading: loading && owned.id === activeId, send, stop, decide };
}
