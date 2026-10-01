// Celkový pohled na proces: co je zelené, co čeká, co blokuje a proč. Kontrakt
// `docs/synchronizace-pravdy.md`, části 5, 8 a 9 — dílek jen zobrazuje hotový `view`, žádné volání
// sítě, žádné vlastní ukládání dat. Rodič drží report a jména rozsahů, dílek jen filtr „jen blokující“.
import { useState } from "react";
import type { DashboardView, ScopeRow } from "@/project/sync-dashboard/logic/sync-dashboard";
import "@/project/sync-dashboard/styles/sync-dashboard.css";

const STATE_LABEL: Record<ScopeRow["state"], string> = {
  waiting: "Čeká na 1:1",
  draft: "Rozpracováno",
  green: "Zelené",
  closed: "Uzavřeno",
};

export default function SyncDashboard({ view, onRefresh }: { view: DashboardView | null; onRefresh?: () => void }) {
  const [onlyBlocking, setOnlyBlocking] = useState(false);
  if (!view) return <p className="sync-dashboard__empty">Echo procesu ještě není načtené.</p>;

  const rows = onlyBlocking ? view.rows.filter((row) => row.failed.length > 0) : view.rows;

  return (
    <section className="sync-dashboard" aria-label="Dashboard procesu" data-testid="sync-dashboard">
      <header className="sync-dashboard__head">
        <div className="sync-dashboard__summary">
          <span className="sync-dashboard__stat sync-dashboard__stat--waiting">Čeká na 1:1: {view.totals.waiting}</span>
          <span className="sync-dashboard__stat sync-dashboard__stat--draft">Rozpracováno: {view.totals.draft}</span>
          <span className="sync-dashboard__stat sync-dashboard__stat--green">Zelené: {view.totals.green}</span>
          <span className="sync-dashboard__stat sync-dashboard__stat--closed">Uzavřeno: {view.totals.closed}</span>
        </div>
        <button type="button" className="sync-dashboard__refresh" onClick={() => onRefresh?.()}>
          Přepočítat
        </button>
      </header>

      <div className="sync-dashboard__severity" aria-label="Echo podle závažnosti">
        <span className="sync-dashboard__severity-item sync-dashboard__severity-item--high">Vysoká: {view.bySeverity.high}</span>
        <span className="sync-dashboard__severity-item sync-dashboard__severity-item--medium">Střední: {view.bySeverity.medium}</span>
        <span className="sync-dashboard__severity-item sync-dashboard__severity-item--low">Nízká: {view.bySeverity.low}</span>
      </div>

      {view.topSignals.length > 0 && (
        <ul className="sync-dashboard__signals" aria-label="Nejčastější echo">
          {view.topSignals.map((signal) => (
            <li key={signal.type} className="sync-dashboard__signal">
              <span className="sync-dashboard__signal-type">{signal.type}</span>
              <span className="sync-dashboard__signal-count">{signal.count}×</span>
            </li>
          ))}
        </ul>
      )}

      <label className="sync-dashboard__filter">
        <input type="checkbox" checked={onlyBlocking} onChange={(event) => setOnlyBlocking(event.target.checked)} />
        Jen blokující
      </label>

      <table className="sync-dashboard__table">
        <thead>
          <tr className="sync-dashboard__row sync-dashboard__row--head">
            <th className="sync-dashboard__cell">Stav</th>
            <th className="sync-dashboard__cell">Rozsah</th>
            <th className="sync-dashboard__cell">Neprošlé kontroly</th>
            <th className="sync-dashboard__cell">Další krok</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className={`sync-dashboard__row sync-dashboard__row--${row.state}`}>
              <td className="sync-dashboard__cell">{STATE_LABEL[row.state]}</td>
              <td className="sync-dashboard__cell">{row.name}</td>
              <td className="sync-dashboard__cell">{row.failed.length > 0 ? row.failed.join(", ") : "—"}</td>
              <td className="sync-dashboard__cell">{row.nextStep ?? "—"}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr className="sync-dashboard__row">
              <td className="sync-dashboard__cell sync-dashboard__cell--empty" colSpan={4}>
                Žádný rozsah neblokuje.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
