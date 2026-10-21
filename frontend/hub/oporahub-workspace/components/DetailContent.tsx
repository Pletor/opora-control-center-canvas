import GraphProposals from "@/hub/graph-proposals/components/GraphProposals";
import ContentChanges from "@/hub/content-changes/components/ContentChanges";
import AcceptancePolicy from "@/hub/proposal-review/components/AcceptancePolicy";
import AcceptanceOverview from "@/hub/proposal-review/components/AcceptanceOverview";
import ReviewPolicy from "@/hub/review-policy/components/ReviewPolicy";
import GithubReconciliation from "@/hub/github-reconciliation/components/GithubReconciliation";
import GitEvidence from "@/hub/git-evidence/components/GitEvidence";
import ExecutionReceipts from "@/hub/execution-receipts/components/ExecutionReceipts";
import ExecutionObservations from "@/hub/execution-observations/components/ExecutionObservations";
import FormalVerification from "@/hub/formal-verification/components/FormalVerification";
import ExecutionBudgets from "@/hub/execution-budgets/components/ExecutionBudgets";
import PlanChanges from "@/hub/plan-changes/components/PlanChanges";
import SyncDashboard from "@/project/sync-dashboard/components/SyncDashboard";
import ProposalHistory from "@/hub/proposal-history/components/ProposalHistory";
import ProcessSync from "@/hub/process-sync/components/ProcessSync";
import { proposeProcessImprovement } from "@/hub/process-sync/logic/process-sync";
import AgentApi from "@/hub/oporahub-overview/components/AgentApi";
import FocusedDetail from "@/hub/oporahub-overview/components/FocusedDetail";
import ExactDetail from "@/hub/oporahub-overview/components/ExactDetail";
import GraphProposalDetails from "@/hub/graph-proposals/components/GraphProposalDetails";
import IdentityPanel from "@/hub/oporahub-identity/components/IdentityPanel";
import ReviewMetrics from "@/hub/oporahub-review-metrics/components/ReviewMetrics";
import ProofLedger from "@/hub/oporahub-proofs/components/ProofLedger";
import ConflictDrawer from "@/hub/oporahub-conflicts/components/ConflictDrawer";
import type { OverviewModels } from "@/hub/oporahub-overview/logic/models";
import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";

export function ExecutionDrawerContent({ models, executionId, onSelect }: {
  models: OverviewModels; executionId: string; onSelect: (executionId: string, title: string) => void;
}) {
  const intentId = models.executionObservations?.items.find(item => item.intent.executionId === executionId)?.intent.id;
  return <>
    <ExactDetail requestedId={executionId} selectedId={models.executions.selected?.executionId} busy={models.executions.busy} error={models.executions.error}>
      <FocusedDetail selector={executionId ? ".execution-receipts__details" : ":not(*)"} revision={`${executionId}:${models.executions.selected?.executionId ?? ""}`}><ExecutionReceipts model={models.executions} /></FocusedDetail>
    </ExactDetail>
    {models.executionObservations && <ExecutionObservations model={models.executionObservations} selectedExecutionId={executionId} selectedIntentId={intentId}
      onSelect={(id) => onSelect(id, `Pozorování běhu · ${models.executionObservations?.items.find(item => item.intent.executionId === id)?.intent.nodeId ?? id}`)} />}
  </>;
}

/** Původní detaily OporaHubu beze změny chování; nový přehled je jen otevírá. */
export default function DetailContent({ models, detail, open, currentAcceptedHead, onChanged }: {
  models: OverviewModels; detail: DetailTarget; open: (target: DetailTarget) => void; currentAcceptedHead: string | null; onChanged?: () => void;
}) {
  const graph = models.graphProposals;
  const project = models.executions.project ?? "", workspace = models.executions.workspace ?? "";
  switch (detail.kind) {
    case "graph": return detail.id ? <section className="graph-proposals">
      {graph.detailBusy && <p role="status">Načítám přesný obsah vybraného návrhu…</p>}
      {graph.detailError && <p role="alert">{graph.detailError}</p>}
      {graph.inspected?.id === detail.id ? <GraphProposalDetails model={graph} review={models.proposalReview?.graph} /> : !graph.detailBusy && !graph.detailError && <p>Vybraný návrh není dostupný. Nebyl nahrazen jiným návrhem.</p>}
    </section> : <GraphProposals model={graph} review={models.proposalReview?.graph} />;
    case "changes": return <ExactDetail requestedId={detail.id} selectedId={models.changes.inspected?.id} busy={models.changes.busy} error={models.changes.error}>
      <FocusedDetail selector={detail.id ? ".plan-changes__inspection" : ":not(*)"} revision={`${detail.id ?? ""}:${models.changes.inspected?.id ?? ""}`}><PlanChanges model={models.changes} review={models.proposalReview?.spec} acceptancePolicy={models.proposalReview?.policy} /></FocusedDetail>
    </ExactDetail>;
    case "executions": return <ExecutionDrawerContent models={models} executionId={detail.id ?? ""} onSelect={(id, title) => open({ kind: "executions", id, title })} />;
    case "evidence": return <ExactDetail requestedId={detail.id} selectedId={models.evidence.selected?.snapshot.id} busy={models.evidence.busy || models.evidence.detailBusy} error={models.evidence.error || models.evidence.detailError}>
      <GitEvidence model={models.evidence} />
    </ExactDetail>;
    case "policy": return <ReviewPolicy model={models.reviewPolicy} />;
    case "tracking": return <GithubReconciliation model={models.reconciliation} />;
    case "budgets": return <ExecutionBudgets model={models.budgets} />;
    case "formal": return <FormalVerification model={models.formalVerification} currentAcceptedHead={currentAcceptedHead} />;
    case "content": return <ContentChanges model={models.contentChanges} requestedId={detail.id} currentAcceptedHead={currentAcceptedHead} review={models.proposalReview?.content} />;
    case "acceptance-policy": return <AcceptancePolicy model={models.proposalReview?.policy} />;
    case "acceptance": return <AcceptanceOverview model={models.proposalReview} open={open} />;
    case "process": return <ProcessSync project={models.executions.project ?? ""} workspace={models.executions.workspace ?? ""} open={open}
      onImprove={(nodeId, name) => proposeProcessImprovement(nodeId, name, models.changes.selectDocument, open)} />;
    case "identity": return <IdentityPanel project={project} />;
    case "review-metrics": return <ReviewMetrics project={project} workspace={workspace} />;
    case "proof-ledger": return <ProofLedger project={project} workspace={workspace} />;
    case "conflicts": return <ConflictDrawer project={project} workspace={workspace} requestedId={detail.id} onResolved={() => onChanged?.()} />;
    case "api": return <AgentApi project={models.executions.project} workspace={models.executions.workspace} />;
    case "history": return <div className="oporahub-workspace__body">
      <GraphProposals model={graph} review={models.proposalReview?.graph} /><PlanChanges model={models.changes} review={models.proposalReview?.spec} acceptancePolicy={models.proposalReview?.policy} />
      <ProposalHistory model={models.proposals} /><SyncDashboard view={models.view} onRefresh={models.onRefresh} />
    </div>;
    default: return null;
  }
}
