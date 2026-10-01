import { useState } from "react";
import { isUuid, parseAllowedPaths } from "@/editor/agent-control/logic/hooks-control";
import type { BindInput } from "@/editor/agent-control/logic/agent-control-api";

type Props = {
  disabled: boolean;
  project: string;
  workspace: string;
  nodeId: string;
  onBind: (input: BindInput) => Promise<void>;
};

const newSessionId = () => crypto.randomUUID();

export default function HookBindingForm({ disabled, project, workspace, nodeId, onBind }: Props) {
  const [sessionId, setSessionId] = useState<string>(newSessionId);
  const [paths, setPaths] = useState("");
  const [maxToolCalls, setMaxToolCalls] = useState("100");
  const [maxFailures, setMaxFailures] = useState("3");
  const [ttlSeconds, setTtlSeconds] = useState("3600");
  const [allowTextSearch, setAllowTextSearch] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);

  const valid = !disabled && confirmed && isUuid(sessionId) && parseAllowedPaths(paths).length > 0 &&
    Number(maxToolCalls) > 0 && Number(maxFailures) > 0 && Number(ttlSeconds) > 0;
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!valid) return;
    setBusy(true);
    try {
      await onBind({ project, workspace, nodeId, sessionId, allowedPaths: parseAllowedPaths(paths), maxToolCalls: Number(maxToolCalls), maxFailures: Number(maxFailures), ttlSeconds: Number(ttlSeconds), allowTextSearch, confirmed: true });
    } finally {
      setBusy(false);
    }
  }

  return <form className="agent-control__form" onSubmit={(event) => void submit(event)}>
    <h3 className="agent-control__heading">Nové připojení Hooku</h3>
    <label className="agent-control__field">Session UUID
      <input value={sessionId} onChange={(event) => setSessionId(event.target.value)} disabled={disabled || busy} aria-label="Session UUID" />
    </label>
    <label className="agent-control__field">Povolené relativní cesty (po řádcích)
      <textarea value={paths} onChange={(event) => setPaths(event.target.value)} disabled={disabled || busy} rows={3} placeholder="frontend/editor" aria-label="Povolené relativní cesty" />
    </label>
    <div className="agent-control__limits">
      <label className="agent-control__field">Nástroje<input type="number" min="1" value={maxToolCalls} onChange={(event) => setMaxToolCalls(event.target.value)} disabled={disabled || busy} /></label>
      <label className="agent-control__field">Selhání<input type="number" min="1" value={maxFailures} onChange={(event) => setMaxFailures(event.target.value)} disabled={disabled || busy} /></label>
      <label className="agent-control__field">TTL s<input type="number" min="1" value={ttlSeconds} onChange={(event) => setTtlSeconds(event.target.value)} disabled={disabled || busy} /></label>
    </div>
    <label className="agent-control__check"><input type="checkbox" checked={allowTextSearch} onChange={(event) => setAllowTextSearch(event.target.checked)} disabled={disabled || busy} /> Povolit cílený textový fallback</label>
    <label className="agent-control__check"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} disabled={disabled || busy} /> Potvrzuji nový běh pro tento UUID a rozsah.</label>
    <button type="submit" className="agent-control__button agent-control__button--primary" disabled={!valid || busy}>{busy ? "Připojuji…" : "Připravit Hook"}</button>
  </form>;
}
