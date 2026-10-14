import type { LiveSession } from "../logic/live-model";
import { sessionView } from "../logic/session-state";

/** Jedna relace jako čip: ikona + „Asistent · čeká na zprávu“, čas posledního signálu v `title`. */
export default function SessionChip({ session }: { session: LiveSession }) {
  const view = sessionView(session);
  return <span className={`live-status__chip live-status__chip--${view.tone}`} title={view.title}>
    <span className="live-status__icon" aria-hidden="true">{view.icon}</span>
    {view.source} · {view.label}
  </span>;
}
