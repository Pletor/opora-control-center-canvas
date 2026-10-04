// Paměť panelu nad úkoly, která nepatří serveru: rozepsané koncepty zpráv a vložené dlaždice per session, kdy uživatel
// který úkol naposledy viděl (značka „nové“), poslední náhled odpovědi a hodiny pro relativní čas.
// Žije jen v paměti panelu; z dat seznamu a konverzace skládá hotové `TaskView` pro dílky.
import { useCallback, useEffect, useMemo, useState } from "react";
import type { AssistantSession } from "./assistant-api";
import type { Conversation } from "./assistant-events";
import type { PastedBlock } from "./pasted-blocks";
import { buildTasks, nextSeen, previewOf, type SeenMap, type TaskView } from "./task-overview";

export type TaskMemory = {
  tasks: TaskView[];
  draft: string;
  setDraft: (id: string, text: string) => void;
  /** Po přijetí zprávy smaže koncept, jen pokud ho uživatel mezitím nepřepsal. */
  clearDraft: (id: string, sent: string) => void;
  pasted: PastedBlock[];
  setPasted: (id: string, blocks: PastedBlock[]) => void;
  /** Po přijetí zprávy odebere odeslané dlaždice; mezitím vložené zůstanou. */
  clearPasted: (id: string, sentIds: string[]) => void;
  /** Změnu, kterou udělal sám uživatel (přejmenování), nehlásit jako „nové“. */
  markSeen: (id: string, updatedAt: string) => void;
};

const NO_BLOCKS: PastedBlock[] = [];

/** `live`: konverzace aktivní session je připojená; jinak se její stav bere ze seznamu session. */
export function useTaskMemory(sessions: AssistantSession[], activeId: string | null, conv: Conversation, live: boolean): TaskMemory {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [pastes, setPastes] = useState<Record<string, PastedBlock[]>>({});
  const [seen, setSeen] = useState<SeenMap>({});
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => { setSeen((s) => nextSeen(s, sessions, activeId)); }, [sessions, activeId]);

  useEffect(() => {
    if (!activeId || !live) return;
    const preview = previewOf(conv.items);
    if (preview) setPreviews((p) => (p[activeId] === preview ? p : { ...p, [activeId]: preview }));
  }, [activeId, conv.items, live]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  const tasks = useMemo(() => {
    const activeState = live ? conv.state : sessions.find((s) => s.id === activeId)?.state ?? "idle";
    const activeItems = live ? conv.items : [];
    return buildTasks(sessions, { activeId, activeState, activeItems, seen, previews, now });
  }, [sessions, activeId, conv.state, conv.items, live, seen, previews, now]);

  const setDraft = useCallback((id: string, text: string) => setDrafts((d) => ({ ...d, [id]: text })), []);
  const clearDraft = useCallback(
    (id: string, sent: string) => setDrafts((d) => ((d[id] ?? "").trim() === sent ? { ...d, [id]: "" } : d)),
    [],
  );

  const setPasted = useCallback((id: string, blocks: PastedBlock[]) => setPastes((p) => ({ ...p, [id]: blocks })), []);
  const clearPasted = useCallback(
    (id: string, sentIds: string[]) => setPastes((p) => ({ ...p, [id]: (p[id] ?? []).filter((b) => !sentIds.includes(b.id)) })),
    [],
  );

  const markSeen = useCallback((id: string, updatedAt: string) => setSeen((s) => ({ ...s, [id]: updatedAt })), []);

  return {
    tasks,
    draft: activeId ? drafts[activeId] ?? "" : "",
    setDraft,
    clearDraft,
    pasted: activeId ? pastes[activeId] ?? NO_BLOCKS : NO_BLOCKS,
    setPasted,
    clearPasted,
    markSeen,
  };
}
