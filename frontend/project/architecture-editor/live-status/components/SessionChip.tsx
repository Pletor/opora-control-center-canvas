import type { LiveSession, WorktreeState } from "../logic/live-model";
import { sessionView } from "../logic/session-state";

/**
 * Jedna relace jako čip: „Asistent · běží“, kde slovo je stav worktree spočítaný backendem. Surový
 * stav zdroje a „naposledy před 4 min“ jsou v `title`. Relace asistenta jde otevřít (`onOpen`);
 * fokus drží strom, proto tlačítko nemá vlastní zastávku Tab.
 */
export default function SessionChip({ session, effective, onOpen }: { session: LiveSession; effective: WorktreeState; onOpen?: () => void }) {
  const view = sessionView(session, effective);
  const className = `live-status__chip live-status__chip--${view.tone}`;
  const body = <><span className="live-status__icon" aria-hidden="true">{view.icon}</span>{view.source} · {view.label}</>;
  if (onOpen && view.openable) {
    return <button type="button" tabIndex={-1} className={className + " live-status__chip--action"} title={view.title + " · otevřít relaci"}
      data-testid={"session-open-" + session.id} onClick={(event) => { event.stopPropagation(); onOpen(); }}>{body}</button>;
  }
  return <span className={className} title={view.title}>{body}</span>;
}
