import GraphProposals from "@/hub/graph-proposals/components/GraphProposals";
import ReviewPolicy from "@/hub/review-policy/components/ReviewPolicy";
import GithubReconciliation from "@/hub/github-reconciliation/components/GithubReconciliation";
import type { GithubReconciliationView } from "@/hub/github-reconciliation/logic/use-github-reconciliation";
import type { ReviewPolicyView } from "@/hub/review-policy/logic/use-review-policy";
import type { GraphProposalsView } from "@/hub/graph-proposals/logic/use-graph-proposals";
// App owns the data and actions; this environment composes independent features.
import GitEvidence from "@/hub/git-evidence/components/GitEvidence";
import ExecutionReceipts from "@/hub/execution-receipts/components/ExecutionReceipts";
import type { ExecutionReceiptsView } from "@/hub/execution-receipts/logic/use-execution-receipts";
import type { GitEvidenceView } from "@/hub/git-evidence/logic/use-git-evidence";
import PlanChanges from "@/hub/plan-changes/components/PlanChanges";
import type { PlanChangesView } from "@/hub/plan-changes/logic/use-plan-changes";
import SyncDashboard from "@/project/sync-dashboard/components/SyncDashboard";
import type { DashboardView } from "@/project/sync-dashboard/logic/sync-dashboard";
import ProposalHistory from "@/hub/proposal-history/components/ProposalHistory";
import type { OporaProposalsView } from "@/hub/proposal-history/logic/use-opora-proposals";
import "@/hub/oporahub-workspace/styles/oporahub-workspace.css";

export default function OporaHubWorkspace({ view, onRefresh, proposals, changes, evidence, executions, graphProposals, reviewPolicy, reconciliation }: {
  view: DashboardView | null; onRefresh: () => void; proposals: OporaProposalsView; changes: PlanChangesView; evidence: GitEvidenceView; executions: ExecutionReceiptsView; graphProposals: GraphProposalsView; reviewPolicy: ReviewPolicyView; reconciliation: GithubReconciliationView;
}) {
  return <section className="oporahub-workspace" aria-label="OporaHub" data-testid="oporahub-workspace">
    <header className="oporahub-workspace__head">
      <h1 className="oporahub-workspace__title">OporaHub</h1>
      <p className="oporahub-workspace__lead">Plán a jeho historie v Canvasu. Kód a jeho ověření v GitHubu.</p>
    </header>
    <div className="oporahub-workspace__body">
      <GraphProposals model={graphProposals} />
      <PlanChanges model={changes} />
      <ExecutionReceipts model={executions} />
      <GitEvidence model={evidence} />
      <ReviewPolicy model={reviewPolicy} />
      <GithubReconciliation model={reconciliation} />
      <ProposalHistory model={proposals} />
      <SyncDashboard view={view} onRefresh={onRefresh} />
    </div>
  </section>;
}
