// Vazba asistenta na React a síť. Hook drží stav, status CLI, seznam session projektu, aktivní
// session a její konverzaci. Konverzaci skládá čistý reducer z assistant-events.ts: nejdřív přepis
// (historie), pak EventSource od `lastSeq` (jen nové události). Přepnutí session starý EventSource
// zavře. Volá ho AssistantPanel; dílky dostávají jen hotová data a callbacky.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  closeSession,
  createSession,
  eventsUrl,
  fetchSessions,
  fetchStatus,
  fetchTranscript,
  sendMessage,
  stopSession,
  type AssistantContext,
  type AssistantModel,
  type AssistantSession,
  type AssistantStatus,
} from "./assistant-api";
import {
  addLocalUserMessage,
  applyEvent,
  emptyConversation,
  failLocalMessage,
  loadTranscript,
  type AssistantEvent,
  type Conversation,
} from "./assistant-events";
import { readDefaultModel, writeDefaultModel } from "./assistant-prefs";

const EVENT_TYPES = ["status", "text_delta", "message", "tool_use", "tool_result", "turn_end", "error", "approval", "approval_resolved"];

export type AssistantApi = {
  status: AssistantStatus | null;
  failure: string;
  sessions: AssistantSession[];
  activeId: string | null;
  conv: Conversation;
  loading: boolean;
  model: AssistantModel;
  setModel: (model: AssistantModel) => void;
  select: (id: string) => void;
  create: () => Promise<void>;
  close: (id: string) => Promise<void>;
  send: (text: string, context: AssistantContext) => Promise<boolean>;
  stop: () => Promise<void>;
};

const messageOf = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function useAssistant(open: boolean, project: string, workspace: string): AssistantApi {
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [failure, setFailure] = useState("");
  const [sessions, setSessions] = useState<AssistantSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [conv, setConv] = useState<Conversation>(emptyConversation());
  const [loading, setLoading] = useState(false);
  const [model, setModelState] = useState<AssistantModel>(readDefaultModel);
  const counter = useRef(0);
  const available = status?.available === true;

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setFailure("");
    fetchStatus().then((s) => alive && setStatus(s)).catch((e) => alive && setFailure(messageOf(e)));
    return () => { alive = false; };
  }, [open]);

  // Seznam session patří projektu; po přepnutí projektu se vybírá znovu.
  useEffect(() => {
    setActiveId(null);
    setSessions([]);
  }, [project]);
  useEffect(() => {
    if (!open || !available || !project) return;
    let alive = true;
    fetchSessions(project)
      .then((list) => {
        if (!alive) return;
        const live = list.filter((s) => s.state !== "closed");
        setSessions(live);
        setActiveId((current) => (current && live.some((s) => s.id === current) ? current : live[0]?.id ?? null));
      })
      .catch((e) => alive && setFailure(messageOf(e)));
    return () => { alive = false; };
  }, [open, available, project]);

  // Historie z přepisu, potom jen nové události; cleanup zavře EventSource staré session.
  useEffect(() => {
    setConv(emptyConversation());
    if (!open || !available || !activeId || !project) return;
    let alive = true;
    let source: EventSource | null = null;
    setLoading(true);
    (async () => {
      const list = await fetchSessions(project);
      const meta = list.find((s) => s.id === activeId);
      const messages = await fetchTranscript(activeId);
      if (!alive) return;
      setConv(loadTranscript(messages, meta?.state ?? "idle", meta?.lastSeq ?? 0));
      setLoading(false);
      const opened = new EventSource(eventsUrl(activeId, meta?.lastSeq ?? 0));
      source = opened;
      const handle = (message: MessageEvent) => {
        try {
          const event = JSON.parse(message.data) as AssistantEvent;
          if (event && typeof event.type === "string") setConv((c) => applyEvent(c, event));
        } catch { /* Poškozený řádek streamu se přeskočí. */ }
      };
      opened.onmessage = handle;
      EVENT_TYPES.forEach((type) => opened.addEventListener(type, handle as EventListener));
    })().catch((e) => {
      if (!alive) return;
      setLoading(false);
      setFailure(messageOf(e));
    });
    return () => { alive = false; source?.close(); };
  }, [open, available, activeId, project]);

  const setModel = useCallback((next: AssistantModel) => { setModelState(next); writeDefaultModel(next); }, []);

  const create = useCallback(async () => {
    try {
      const session = await createSession({ project, workspace, model });
      setSessions((list) => [...list, session]);
      setActiveId(session.id);
    } catch (e) { setFailure(messageOf(e)); }
  }, [project, workspace, model]);

  const close = useCallback(async (id: string) => {
    try { await closeSession(id); } catch (e) { setFailure(messageOf(e)); return; }
    setSessions((list) => list.filter((s) => s.id !== id));
    setActiveId((current) => (current === id ? null : current));
  }, []);
  // Po zavření aktivní záložky se vybere první zbývající.
  useEffect(() => {
    if (!activeId && sessions.length) setActiveId(sessions[0].id);
  }, [activeId, sessions]);

  const send = useCallback(async (text: string, context: AssistantContext) => {
    if (!activeId) return false;
    const localId = `local-${++counter.current}`;
    setConv((c) => addLocalUserMessage(c, text, localId));
    try {
      await sendMessage(activeId, text, context);
      return true;
    } catch (e) {
      // Backend vrací české důvody (běžící tah, limit procesů, neplatný kontext); ukážou se beze změny.
      setConv((c) => failLocalMessage(c, localId, messageOf(e), "idle"));
      return false;
    }
  }, [activeId]);

  const stop = useCallback(async () => {
    if (!activeId) return;
    try {
      await stopSession(activeId);
      setConv((c) => ({ ...c, state: "idle" }));
    } catch (e) { setFailure(messageOf(e)); }
  }, [activeId]);

  return { status, failure, sessions, activeId, conv, loading, model, setModel, select: setActiveId, create, close, send, stop };
}
