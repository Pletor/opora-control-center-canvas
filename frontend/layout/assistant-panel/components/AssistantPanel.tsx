import { useCallback, useEffect, useRef, useState } from "react";
import type { AssistantContext } from "../logic/assistant-api";
import { isBusy } from "../logic/assistant-events";
import { readPrefs, reopenSize, smallerSize, writePrefs, type PanelSize } from "../logic/assistant-prefs";
import { anyWorking, neighbourTask } from "../logic/task-overview";
import { useAssistantSessions } from "../logic/use-assistant-sessions";
import { useConversation } from "../logic/use-conversation";
import { usePanelKeys } from "../logic/use-panel-keys";
import { useTaskMemory } from "../logic/use-task-memory";
import Composer from "./Composer";
import Conversation from "./Conversation";
import MinimizedBar from "./MinimizedBar";
import PanelNotice from "./PanelNotice";
import SizeSwitch from "./SizeSwitch";
import TaskList from "./TaskList";
import TasksEmpty from "./TasksEmpty";

/**
 * Rodič asistenta: drží velikost (uloženou jednou pro aplikaci), spojení se session a konverzací,
 * koncepty zpráv a zkratky. Dílky dostávají hotová data a hlásí volby nahoru. Zůstává připojený
 * i zavřený (`open=false` nic nevykreslí), aby tlačítko v liště vědělo, že nějaký úkol ještě pracuje.
 */
export default function AssistantPanel({
  open,
  context,
  onClose,
  onBusyChange,
}: {
  open: boolean;
  context: AssistantContext;
  onClose: () => void;
  onBusyChange: (busy: boolean) => void;
}) {
  const [size, setSizeState] = useState<PanelSize>(() => readPrefs().size);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [watch, setWatch] = useState(false);
  const lastExpanded = useRef<PanelSize>(size === "full" ? "full" : "side");
  const root = useRef<HTMLElement>(null);

  const s = useAssistantSessions(open, watch, context.projectId, context.workspace);
  const c = useConversation(open && s.status?.available === true, context.projectId, s.activeId, s.setFailure);
  const memory = useTaskMemory(s.sessions, s.activeId, c.conv, open);
  const { tasks } = memory;
  const working = anyWorking(tasks);

  const setSize = useCallback((next: PanelSize) => {
    setSizeState(next);
    writePrefs({ size: next });
    if (next !== "minimized") lastExpanded.current = next;
  }, []);

  // Otevření tlačítkem: poslední velikost, z lišty rovnou panel vpravo.
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open && !wasOpen.current) setSizeState((current) => reopenSize(current));
    wasOpen.current = open;
  }, [open]);

  // Zavřený panel sleduje seznam jen do chvíle, než všechno doběhne; tečka v liště tak nelže.
  useEffect(() => {
    setWatch(working);
    onBusyChange(working);
  }, [working, onBusyChange]);

  const shrink = useCallback(() => setSize(smallerSize(size)), [setSize, size]);
  const ids = tasks.map((t) => t.id).join("\n");
  const step = useCallback(
    (direction: -1 | 1) => {
      const next = neighbourTask(ids ? ids.split("\n") : [], s.activeId, direction);
      if (next) s.select(next);
    },
    [ids, s.activeId, s.select],
  );
  usePanelKeys(open, root, shrink, step);

  const activeId = s.activeId;
  const send = useCallback(
    async (text: string) => {
      if (!activeId) return;
      if (await c.send(text, context)) memory.clearDraft(activeId, text);
    },
    [activeId, c.send, context, memory.clearDraft],
  );
  const createWith = useCallback(
    async (text: string) => {
      const session = await s.create();
      if (session && text) memory.setDraft(session.id, text);
    },
    [s.create, memory.setDraft],
  );
  const rename = useCallback(
    async (id: string, title: string) => {
      const session = await s.rename(id, title);
      if (session) memory.markSeen(session.id, session.updatedAt);
      return session !== null;
    },
    [s.rename, memory.markSeen],
  );
  const select = useCallback((id: string) => { s.select(id); setDrawerOpen(false); }, [s.select]);

  if (!open) return null;
  const activeTask = tasks.find((t) => t.active) ?? null;
  if (size === "minimized") {
    return (
      <MinimizedBar
        barRef={root}
        task={activeTask}
        count={tasks.length}
        othersNew={tasks.some((t) => t.isNew)}
        onExpand={() => setSize(lastExpanded.current)}
        onClose={onClose}
      />
    );
  }

  let content;
  if (!context.projectId) content = <PanelNotice kind="project" />;
  else if (s.failure && !s.status) content = <PanelNotice kind="failure" detail={s.failure} />;
  else if (!s.status) content = <PanelNotice kind="checking" />;
  else if (!s.status.available) content = <PanelNotice kind="unavailable" />;
  else {
    const empty = s.sessions.length === 0;
    content = (
      <>
        {(size === "full" || !empty) && (
          <TaskList
            variant={size === "full" ? "column" : "drawer"}
            tasks={tasks}
            expanded={drawerOpen}
            model={s.model}
            onToggle={() => setDrawerOpen((v) => !v)}
            onModel={s.setModel}
            onCreate={() => void createWith("")}
            onSelect={select}
            onRename={rename}
            onClose={(id) => void s.close(id)}
          />
        )}
        <section className="assistant-panel__main" aria-label={activeTask ? `Úkol ${activeTask.title}` : "Asistent"}>
          {s.failure && (
            <p role="alert" className="assistant-panel__error assistant-panel__error--banner">
              <span className="assistant-panel__error-text">{s.failure}</span>
              <button type="button" className="assistant-panel__error-dismiss" aria-label="Skrýt chybu" onClick={() => s.setFailure("")}>×</button>
            </p>
          )}
          {empty ? (
            <TasksEmpty withCreate={size !== "full"} model={s.model} onModel={s.setModel} onCreate={() => void createWith("")} onExample={(text) => void createWith(text)} />
          ) : (
            <>
              <Conversation conv={c.conv} loading={c.loading} sessionKey={activeId ?? ""} />
              <Composer
                value={memory.draft}
                busy={isBusy(c.conv.state)}
                disabled={!activeId}
                focusKey={activeId ?? ""}
                onChange={(text) => activeId && memory.setDraft(activeId, text)}
                onSend={(text) => void send(text)}
                onStop={() => void c.stop()}
              />
            </>
          )}
        </section>
      </>
    );
  }

  return (
    <aside ref={root} className={`assistant-panel assistant-panel--${size}`} aria-label="Asistent">
      <header className="assistant-panel__head">
        <span className="assistant-panel__brand">Asistent</span>
        <SizeSwitch size={size} onSize={setSize} />
        <button type="button" className="assistant-panel__close" aria-label="Zavřít asistenta" title="Zavřít asistenta" onClick={onClose}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" />
          </svg>
        </button>
      </header>
      <div className="assistant-panel__body">{content}</div>
    </aside>
  );
}
