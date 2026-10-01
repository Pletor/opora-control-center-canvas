import { useEffect } from "react";
import { useAssistant } from "../logic/use-assistant";
import { isBusy } from "../logic/assistant-events";
import type { AssistantContext } from "../logic/assistant-api";
import SessionTabs from "./SessionTabs";
import MessageList from "./MessageList";
import Composer from "./Composer";

/**
 * Rodič panelu: drží spojení a stav konverzace (hook `useAssistant`) a skládá dílky. Kontext plátna
 * (projekt, workspace, vrstva, výběr, prostředí) dostane od App a ke každé zprávě ho přiloží.
 */
export default function AssistantPanel({ context, onClose }: { context: AssistantContext; onClose: () => void }) {
  const a = useAssistant(true, context.projectId, context.workspace);
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);

  let body;
  if (!context.projectId) {
    body = <p className="assistant-panel__notice">Nejdřív vyberte projekt v horní liště.</p>;
  } else if (a.failure && !a.status) {
    body = <p role="alert" className="assistant-panel__notice assistant-panel__notice--error">Asistent není dostupný: {a.failure}</p>;
  } else if (!a.status) {
    body = <p className="assistant-panel__notice">Zjišťuji, jestli je Claude Code k dispozici…</p>;
  } else if (!a.status.available) {
    body = (
      <p className="assistant-panel__notice assistant-panel__notice--error" role="alert">
        Claude Code (<code>claude</code>) není nainstalovaný nebo přihlášený. Otevřete terminál, spusťte příkaz <code>claude</code> a přihlaste se, potom panel otevřete znovu.
      </p>
    );
  } else {
    const busy = isBusy(a.conv.state);
    body = (
      <>
        <SessionTabs
          sessions={a.sessions}
          activeId={a.activeId}
          activeState={a.conv.state}
          model={a.model}
          onSelect={a.select}
          onClose={(id) => void a.close(id)}
          onModel={a.setModel}
          onCreate={() => void a.create()}
        />
        {a.failure && <p role="alert" className="assistant-panel__error">{a.failure}</p>}
        {a.activeId ? (
          <MessageList conv={a.conv} loading={a.loading} />
        ) : (
          <p className="assistant-panel__notice">Žádná session. Založte ji tlačítkem „+ Nová session“.</p>
        )}
        <Composer busy={busy} disabled={!a.activeId} onSend={(text) => a.send(text, context)} onStop={() => void a.stop()} />
      </>
    );
  }
  return (
    <aside className="assistant-panel" role="complementary" aria-label="Asistent">
      <header className="assistant-panel__head">
        <strong className="assistant-panel__title">Asistent</strong>
        <button type="button" className="assistant-panel__close" aria-label="Zavřít asistenta" onClick={onClose}>×</button>
      </header>
      {body}
    </aside>
  );
}
