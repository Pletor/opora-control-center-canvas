// App owns the data and actions; this environment composes independent features.
import PlanChanges from "@/hub/plan-changes/components/PlanChanges";
import type { PlanChangesView } from "@/hub/plan-changes/logic/use-plan-changes";
import SyncDashboard from "@/project/sync-dashboard/components/SyncDashboard";
import type { DashboardView } from "@/project/sync-dashboard/logic/sync-dashboard";
import ProposalHistory from "@/hub/proposal-history/components/ProposalHistory";
import type { OporaProposalsView } from "@/hub/proposal-history/logic/use-opora-proposals";
import "@/hub/oporahub-workspace/styles/oporahub-workspace.css";

export default function OporaHubWorkspace({ view, onRefresh, proposals, changes }: {
  view: DashboardView | null; onRefresh: () => void; proposals: OporaProposalsView; changes: PlanChangesView;
}) {
  return <section className="oporahub-workspace" aria-label="OporaHub" data-testid="oporahub-workspace">
    <header className="oporahub-workspace__head">
      <h1 className="oporahub-workspace__title">OporaHub</h1>
      <p className="oporahub-workspace__lead">Plán a jeho historie v Canvasu. Kód a jeho ověření v GitHubu.</p>
    </header>
    <div className="oporahub-workspace__body">
      <PlanChanges model={changes} />
      <ProposalHistory model={proposals} />
      <SyncDashboard view={view} onRefresh={onRefresh} />
    </div>
  </section>;
}
