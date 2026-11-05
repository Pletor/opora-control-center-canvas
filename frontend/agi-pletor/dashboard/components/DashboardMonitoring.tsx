import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { monitoringView } from "../logic/monitoring-view";

const POLL_MS = 10000;

/** Monitoring: zapnuto/vypnuto, hosté a poslední události plátna 4 z `GET /api/pletor/monitoring`, čte se každých 10 s. */
export default function DashboardMonitoring({ project }: { project: string }) {
  const [raw, setRaw] = useState<unknown>(null);
  const [error, setError] = useState("");
  usePolling(() => api<unknown>(`/api/pletor/monitoring?${new URLSearchParams({ project })}`).then(
    (next) => { setRaw(next); setError(""); },
    (failure: unknown) => setError(failure instanceof Error ? failure.message : "Načtení selhalo."),
  ), { intervalMs: POLL_MS, enabled: !!project, refreshKeys: [project] });
  const view = monitoringView(raw);
  return (
    <>
      <p><span className="pletor-dashboard__tag">{view.enabled ? "zapnuto" : "vypnuto"}</span></p>
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      {view.problem && <p className="pletor-dashboard__error">{view.problem}</p>}
      <h2 className="pletor-dashboard__group-title">Hosté</h2>
      <table className="pletor-dashboard__table">
        <thead><tr><th>Host</th><th>Stav</th></tr></thead>
        <tbody>
          {view.hosts.map((row) => <tr key={row.host}><td>{row.host}</td><td>{row.state}</td></tr>)}
          {view.hosts.length === 0 && <tr><td colSpan={2} className="pletor-dashboard__empty">Žádní hosté.</td></tr>}
        </tbody>
      </table>
      <h2 className="pletor-dashboard__group-title">Poslední události plátna 4</h2>
      <table className="pletor-dashboard__table">
        <thead><tr><th>Čas</th><th>Typ</th><th>Autor</th><th>Payload</th></tr></thead>
        <tbody>
          {view.events.map((row, index) => <tr key={index}><td>{row.ts}</td><td>{row.type}</td><td>{row.author}</td><td className="pletor-dashboard__mono">{row.payload}</td></tr>)}
          {view.events.length === 0 && <tr><td colSpan={4} className="pletor-dashboard__empty">Žádné události.</td></tr>}
        </tbody>
      </table>
    </>
  );
}
