import type { LiveSession, WorktreeState } from "../logic/live-model";
import { sessionView } from "../logic/session-state";

/**
 * Jedna relace jako čip: „Karta · běží“, kde slovo je stav worktree spočítaný backendem. Surový
 * stav zdroje a „naposledy před 4 min“ jsou v `title`.
 */
export default function SessionChip({ session, effective }: { session: LiveSession; effective: WorktreeState }) {
  const view = sessionView(session, effective);
  return <span className={`live-status__chip live-status__chip--${view.tone}`} title={view.title}>
    <span className="live-status__icon" aria-hidden="true">{view.icon}</span>{view.source} · {view.label}
  </span>;
}
