import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AssistantContext, AssistantScope, ViewContext } from "../logic/assistant-api";
import { isBusy } from "../logic/assistant-events";
import { readPrefs, reopenSize, smallerSize, writePrefs, type PanelSize } from "../logic/assistant-prefs";
import { anyWorking, groupTasks, neighbourTask } from "../logic/task-overview";
import { useAssistantSessions } from "../logic/use-assistant-sessions";
import { useConversation } from "../logic/use-conversation";
import { usePanelKeys } from "../logic/use-panel-keys";
import { useTaskMemory } from "../logic/use-task-memory";
import { useTaskOutline } from "../logic/use-task-outline";
import { useStartRequest, type StartRequest } from "../logic/use-start-request";
import Composer from "./Composer";
import Conversation from "./Conversation";
import MinimizedBar from "./MinimizedBar";
import Outline from "./Outline";
import PanelHead from "./PanelHead";
import PanelNotice from "./PanelNotice";
import TaskColumn from "./TaskColumn";
import TaskList from "./TaskList";
import TasksEmpty from "./TasksEmpty";

/**
 * Rodič asistenta: drží velikost (uloženou jednou pro aplikaci), spojení se session a konverzací,
 * koncepty zpráv a zkratky. Dílky dostávají hotová data a hlásí volby nahoru. Zůstává připojený
 * i zavřený (`open=false` nic nevykreslí), aby tlačítko v liště vědělo, že nějaký úkol ještě pracuje.
 * Na celé ploše skládá tři sloupce: úkoly, konverzaci po tazích a osnovu (tu skrývá CSS pod 1280 px).
 * K pohledu od App přidá rozsah práce (preference aplikace, §6.1) a povolený zápis, který doběhl,
 * ohlásí nahoru `onCanvasWritten`, aby rodič načetl plátno znovu (§6.2).
 */
export default function AssistantPanel({
  open,
  context: view,
  onClose,
  onBusyChange,
  onCanvasWritten,
  startRequest,
}: {
  open: boolean;
  context: ViewContext;
  onClose: () => void;
  onBusyChange: (busy: boolean) => void;
  onCanvasWritten: () => void;
  /** Nový úkol zvenku (živý panel domény); založí se jednou, bez zprávy. */
  startRequest?: StartRequest | null;
}) {
  const [size, setSizeState] = useState<PanelSize>(() => readPrefs().size);
  const [scope, setScopeState] = useState<AssistantScope>(() => readPrefs().scope);
  const setScope = useCallback((next: AssistantScope) => { setScopeState(next); writePrefs({ scope: next }); }, []);
  const context = useMemo<AssistantContext>(() => ({ ...view, scope }), [view, scope]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [watch, setWatch] = useState(false);
  const lastExpanded = useRef<PanelSize>(size === "full" ? "full" : "side");
  const root = useRef<HTMLElement>(null);

  const s = useAssistantSessions(open, watch, context.projectId, context.workspace);
  useStartRequest(startRequest, open && s.status?.available === true, s.create);
  const c = useConversation(open && s.status?.available === true, context.projectId, s.activeId, s.setFailure, onCanvasWritten);
  const memory = useTaskMemory(s.sessions, s.activeId, c.conv, open);
  const { tasks } = memory;
  const working = anyWorking(tasks);
  const outline = useTaskOutline(c.conv.items, s.activeId);

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
  // Na celé ploše jdou Alt+šipky v pořadí skupin, jak je uživatel vidí.
  const ordered = size === "full" ? groupTasks(tasks).flatMap((g) => g.tasks) : tasks;
  const ids = ordered.map((t) => t.id).join("\n");
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
    async (message: string, draft: string, blockIds: string[]) => {
      if (!activeId) return;
      if (await c.send(message, context)) {
        memory.clearDraft(activeId, draft);
        memory.clearPasted(activeId, blockIds);
        outline.rememberSent(activeId, context);
      }
    },
    [activeId, c.send, context, memory.clearDraft, memory.clearPasted, outline.rememberSent],
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
        {size === "full" ? (
          <TaskColumn
            tasks={tasks}
            model={s.model}
            onModel={s.setModel}
            onCreate={() => void createWith("")}
            onSelect={select}
            onRename={rename}
            onClose={(id) => void s.close(id)}
          />
        ) : (
          !empty && (
            <TaskList
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
          )
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
              <Conversation conv={c.conv} turns={outline.turns} loading={c.loading} sessionKey={activeId ?? ""} onActiveTurn={outline.setActiveTurn} onDecide={(id, decision, note) => void c.decide(id, decision, note)} />
              <Composer
                value={memory.draft}
                pasted={memory.pasted}
                busy={isBusy(c.conv.state)}
                disabled={!activeId}
                focusKey={activeId ?? ""}
                label={size === "full" && activeTask ? `Odpověď do úkolu „${activeTask.title}“` : undefined}
                scope={scope}
                selectedCount={context.selectedNodeIds.length}
                onScope={setScope}
                onChange={(text) => activeId && memory.setDraft(activeId, text)}
                onPastedChange={(blocks) => activeId && memory.setPasted(activeId, blocks)}
                onSend={(message, draft, blockIds) => void send(message, draft, blockIds)}
                onStop={() => void c.stop()}
              />
            </>
          )}
        </section>
        {size === "full" && !empty && (
          <Outline
            context={outline.sentContext ?? context}
            contextSent={outline.sentContext !== null}
            turns={outline.turns}
            activeTurn={outline.activeTurn}
            decisions={outline.decisions}
            steps={outline.steps}
            onJump={outline.jump}
          />
        )}
      </>
    );
  }

  return (
    <aside ref={root} className={`assistant-panel assistant-panel--${size}`} aria-label="Asistent">
      <PanelHead size={size} task={activeTask} onSize={setSize} onClose={onClose} />
      <div className="assistant-panel__body">{content}</div>
    </aside>
  );
}
