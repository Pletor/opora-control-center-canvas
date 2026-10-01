import { useState } from "react";
import type { HookBinding, HookEvent } from "@/editor/agent-control/logic/hooks-control";
import { bindingAvailability, canControlBinding } from "@/editor/agent-control/logic/hooks-control";

type Props = {
  bindings: HookBinding[];
  readOnly: boolean;
  disabled: boolean;
  expandedId: string | null;
  events: HookEvent[];
  eventsTruncated: boolean;
  onExpanded: (bindingId: string | null) => void;
  onControl: (binding: HookBinding, action: "pause" | "resume" | "stop") => Promise<void>;
};

export default function HookBindingList({ bindings, readOnly, disabled, expandedId, events, eventsTruncated, onExpanded, onControl }: Props) {
  const [busy, setBusy] = useState(false);
  async function control(binding: HookBinding, action: "pause" | "resume" | "stop") {
    if (busy || disabled || !canControlBinding(readOnly, binding, action) || !window.confirm(`${action.toUpperCase()} binding ${binding.id} v${binding.revision}?`)) return;
    setBusy(true);
    try { await onControl(binding, action); } finally { setBusy(false); }
  }
  if (!bindings.length) return <p className="agent-control__note">Pro tento uzel zatím není připravené žádné připojení.</p>;
  return <section className="agent-control__bindings" aria-label="Připojení Hooku">
    <h3 className="agent-control__heading">Připojení</h3>
    {bindings.map((binding) => {
      const open = expandedId === binding.id;
      const controlAllowed = !disabled && !busy;
      const pauseAllowed = controlAllowed && canControlBinding(readOnly, binding, "pause");
      const resumeAllowed = controlAllowed && canControlBinding(readOnly, binding, "resume");
      const stopAllowed = controlAllowed && canControlBinding(readOnly, binding, "stop");
      return <article className="agent-control__binding" key={binding.id}>
        <button type="button" className="agent-control__binding-head" onClick={() => onExpanded(open ? null : binding.id)} aria-expanded={open} disabled={busy}>
          <strong>{bindingAvailability(binding)}</strong><span>{binding.state} · revize {binding.revision}</span>
        </button>
        <p className="agent-control__meta">Schváleno/aktuální/ACK: {binding.approvedTaskRevision}/{binding.currentTaskRevision}/{binding.acknowledgedRevision ?? "—"}</p>
        <p className="agent-control__meta">Nástroje {binding.toolCalls}/{binding.maxToolCalls} · selhání za sebou {binding.consecutiveFailures}/{binding.maxFailures}</p>
        <p className="agent-control__meta">Poslední: {binding.lastDecision ?? "bez rozhodnutí"} · {binding.lastEvent ?? "bez události"}</p>
        {binding.lastSeenAt && <p className="agent-control__meta">Viděn: {binding.lastSeenAt} · platí do {binding.expiresAt}</p>}
        <div className="agent-control__actions">
          <button type="button" className="agent-control__button" disabled={!pauseAllowed || binding.state !== "active"} onClick={() => void control(binding, "pause")}>Pause</button>
          <button type="button" className="agent-control__button" disabled={!resumeAllowed || binding.state !== "paused"} onClick={() => void control(binding, "resume")}>Resume</button>
          <button type="button" className="agent-control__button agent-control__button--danger" disabled={!stopAllowed} onClick={() => void control(binding, "stop")}>Stop</button>
        </div>
        {binding.state !== "stopped" && <p className="agent-control__warning">Stop zastaví další zpracování při příštím hooku; neukončuje OS proces.</p>}
        {open && <div className="agent-control__events">
          <p className="agent-control__meta">Povolené cesty: {binding.allowedPaths.join(", ") || "—"}</p>
          {events.map((event) => <p className="agent-control__event" key={event.id}>{event.at} · {event.event} · {event.toolName ?? "—"} · {event.decision ?? "—"}{event.reason ? ` · ${event.reason}` : ""}</p>)}
          {!events.length && <p className="agent-control__note">Zatím žádné bezpečně publikované události.</p>}
          {eventsTruncated && <p className="agent-control__warning">Timeline je zkrácená na poslední události.</p>}
        </div>}
      </article>;
    })}
  </section>;
}
