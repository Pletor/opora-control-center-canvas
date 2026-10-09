// Prostředí OporaHub (Alt+3): plán a dokumentace držené 1:1 s kódem. Zatím skládá jen celkový
// pohled na proces (`SyncDashboard`). Dílek nic nenačítá: report i obnovu dostává od rodiče (App).
import SyncDashboard from "@/project/sync-dashboard/components/SyncDashboard";
import type { DashboardView } from "@/project/sync-dashboard/logic/sync-dashboard";
import "@/hub/oporahub-workspace/styles/oporahub-workspace.css";

export default function OporaHubWorkspace({ view, onRefresh }: { view: DashboardView | null; onRefresh: () => void }) {
  return (
    <section className="oporahub-workspace" aria-label="OporaHub" data-testid="oporahub-workspace">
      <header className="oporahub-workspace__head">
        <h1 className="oporahub-workspace__title">OporaHub</h1>
        <p className="oporahub-workspace__lead">Pravda je v GitHubu. OporaHub drží plán a dokumentaci 1:1 s kódem.</p>
      </header>
      <div className="oporahub-workspace__body">
        <SyncDashboard view={view} onRefresh={onRefresh} />
      </div>
    </section>
  );
}
