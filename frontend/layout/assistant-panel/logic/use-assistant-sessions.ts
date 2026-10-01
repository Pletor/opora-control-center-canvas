// Vazba seznamu úkolů (session) na React a síť: status CLI, session projektu, aktivní session, výchozí
// model a akce založit / přejmenovat / zavřít. Seznam se obnovuje pollingem `GET sessions` každé
// 4 s, jen když je panel otevřený (i jako lišta) nebo když při zavření ještě něco pracovalo; tak se
// stav ostatních úkolů mění i bez otevření jejich konverzace. Volá ho jen AssistantPanel.
import { useCallback, useEffect, useState } from "react";
import {
  closeSession,
  createSession,
  fetchSessions,
  fetchStatus,
  renameSession,
  type AssistantModel,
  type AssistantSession,
  type AssistantStatus,
} from "./assistant-api";
import { readPrefs, writePrefs } from "./assistant-prefs";

const POLL_MS = 4000;

export const messageOf = (error: unknown) => (error instanceof Error ? error.message : String(error));

export type SessionsApi = {
  status: AssistantStatus | null;
  failure: string;
  setFailure: (text: string) => void;
  sessions: AssistantSession[];
  activeId: string | null;
  select: (id: string) => void;
  model: AssistantModel;
  setModel: (model: AssistantModel) => void;
  create: () => Promise<AssistantSession | null>;
  close: (id: string) => Promise<void>;
  rename: (id: string, title: string) => Promise<AssistantSession | null>;
};

function same(a: AssistantSession[], b: AssistantSession[]): boolean {
  return a.length === b.length && a.every((s, i) => s.id === b[i].id && s.updatedAt === b[i].updatedAt && s.state === b[i].state && s.title === b[i].title);
}

export function useAssistantSessions(open: boolean, watch: boolean, project: string, workspace: string): SessionsApi {
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [failure, setFailure] = useState("");
  const [sessions, setSessions] = useState<AssistantSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [model, setModelState] = useState<AssistantModel>(() => readPrefs().model);
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

  const polling = (open || watch) && available && !!project;
  useEffect(() => {
    if (!polling) return;
    let alive = true;
    const load = () =>
      fetchSessions(project)
        .then((list) => {
          if (!alive) return;
          const live = list.filter((s) => s.state !== "closed");
          setSessions((current) => (same(current, live) ? current : live));
          setActiveId((current) => (current && live.some((s) => s.id === current) ? current : live[0]?.id ?? null));
        })
        .catch((e) => alive && setFailure(messageOf(e)));
    void load();
    const timer = window.setInterval(load, POLL_MS);
    return () => { alive = false; window.clearInterval(timer); };
  }, [polling, project]);

  const setModel = useCallback((next: AssistantModel) => { setModelState(next); writePrefs({ model: next }); }, []);

  const create = useCallback(async () => {
    try {
      const session = await createSession({ project, workspace, model });
      setSessions((list) => [...list, session]);
      setActiveId(session.id);
      return session;
    } catch (e) {
      setFailure(messageOf(e));
      return null;
    }
  }, [project, workspace, model]);

  const close = useCallback(async (id: string) => {
    try { await closeSession(id); } catch (e) { setFailure(messageOf(e)); return; }
    const index = sessions.findIndex((s) => s.id === id);
    const rest = sessions.filter((s) => s.id !== id);
    setSessions((list) => list.filter((s) => s.id !== id));
    // Po zavření aktivního úkolu se vybere soused, ať uživatel nezůstane v prázdnu.
    setActiveId((current) => (current === id ? rest[Math.min(index, rest.length - 1)]?.id ?? null : current));
  }, [sessions]);

  const rename = useCallback(async (id: string, title: string) => {
    try {
      const session = await renameSession(id, title);
      setSessions((list) => list.map((s) => (s.id === id ? { ...s, ...session } : s)));
      return session;
    } catch (e) {
      setFailure(messageOf(e));
      return null;
    }
  }, []);

  return { status, failure, setFailure, sessions, activeId, select: setActiveId, model, setModel, create, close, rename };
}
