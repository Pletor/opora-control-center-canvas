import { useState } from "react";
import GraphProposals from "@/hub/graph-proposals/components/GraphProposals";
import { useEffect } from "react";
import ContentChanges from "@/hub/content-changes/components/ContentChanges";
import AcceptancePolicy from "@/hub/proposal-review/components/AcceptancePolicy";
import ReviewPolicy from "@/hub/review-policy/components/ReviewPolicy";
import GithubReconciliation from "@/hub/github-reconciliation/components/GithubReconciliation";
import GitEvidence from "@/hub/git-evidence/components/GitEvidence";
import ExecutionReceipts from "@/hub/execution-receipts/components/ExecutionReceipts";
import ExecutionObservations from "@/hub/execution-observations/components/ExecutionObservations";
import FormalVerification from "@/hub/formal-verification/components/FormalVerification";
import { acceptedPlan } from "@/hub/oporahub-overview/logic/overview";
import ExecutionBudgets from "@/hub/execution-budgets/components/ExecutionBudgets";
import PlanChanges from "@/hub/plan-changes/components/PlanChanges";
import SyncDashboard from "@/project/sync-dashboard/components/SyncDashboard";
import ProposalHistory from "@/hub/proposal-history/components/ProposalHistory";
import OporaHubOverview from "@/hub/oporahub-overview/components/OporaHubOverview";
import OverviewDrawer from "@/hub/oporahub-overview/components/OverviewDrawer";
import AgentApi from "@/hub/oporahub-overview/components/AgentApi";
import FocusedDetail from "@/hub/oporahub-overview/components/FocusedDetail";
import ExactDetail from "@/hub/oporahub-overview/components/ExactDetail";
import GraphProposalDetails from "@/hub/graph-proposals/components/GraphProposalDetails";
import type { OverviewModels } from "@/hub/oporahub-overview/logic/models";
import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import "@/hub/oporahub-workspace/styles/oporahub-workspace.css";

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

// App owns all data, requests and mutations. This environment only composes its features.
export default function OporaHubWorkspace(models: OverviewModels) {
  const plan = acceptedPlan(models.graphProposals.context, models.changes.context);
  const currentAcceptedHead = !models.graphProposals.busy && !models.changes.busy && !models.graphProposals.error && !models.changes.error && plan.basisKnown ? plan.head : null;
  const scope = JSON.stringify([models.executions.project, models.executions.workspace]);
  const [selection, setSelection] = useState<{ scope: string; target: DetailTarget } | null>(null);
  const detail = selection?.scope === scope ? selection.target : null;
  useEffect(() => {
    const id = models.contentChanges?.selectedId;
    if (detail?.kind === "content" && detail.id && id && id !== detail.id && models.contentChanges?.detail?.proposal.id === id)
      setSelection({ scope, target: { kind: "content", id, title: "Změny obsahu · nový návrh" } });
  }, [scope, detail, models.contentChanges?.selectedId, models.contentChanges?.detail?.proposal.id]);
  function open(target: DetailTarget) {
    if (target.id) {
      if (target.kind === "graph") models.graphProposals.inspect(target.id);
      if (target.kind === "changes") models.changes.inspect(target.id);
      if (target.kind === "executions") models.executions.selectExecution(target.id);
      if (target.kind === "evidence") models.evidence.select(target.id);
      if (target.kind === "formal") models.formalVerification.select(target.id);
      if (target.kind === "content") models.contentChanges?.select(target.id);
    }
    if (target.kind === "content" && !target.id) models.contentChanges?.cancel();
    setSelection({ scope, target });
  }
  function close() { models.proposalReview?.reset(); models.contentChanges?.cancel(); models.budgets.cancel(); models.executions.dismissCancel(); models.reviewPolicy.cancel(); models.reconciliation.cancel(); models.graphProposals.acknowledge(false); setSelection(null); }
  return <section className="oporahub-workspace" aria-label="OporaHub" data-testid="oporahub-workspace">
    <OporaHubOverview models={models} open={open} />
    {detail && <OverviewDrawer title={detail.title} onClose={close}>
      {detail.kind === "graph" && (detail.id ? <section className="graph-proposals">
        {models.graphProposals.detailBusy && <p role="status">Načítám přesný obsah vybraného návrhu…</p>}
        {models.graphProposals.detailError && <p role="alert">{models.graphProposals.detailError}</p>}
        {models.graphProposals.inspected?.id === detail.id ? <GraphProposalDetails model={models.graphProposals} review={models.proposalReview?.graph} /> : !models.graphProposals.detailBusy && !models.graphProposals.detailError && <p>Vybraný návrh není dostupný. Nebyl nahrazen jiným návrhem.</p>}
      </section> : <GraphProposals model={models.graphProposals} review={models.proposalReview?.graph} />)}
      {detail.kind === "changes" && <ExactDetail requestedId={detail.id} selectedId={models.changes.inspected?.id} busy={models.changes.busy} error={models.changes.error}>
        <FocusedDetail selector={detail.id ? ".plan-changes__inspection" : ":not(*)"} revision={`${detail.id ?? ""}:${models.changes.inspected?.id ?? ""}`}><PlanChanges model={models.changes} review={models.proposalReview?.spec} acceptancePolicy={models.proposalReview?.policy} /></FocusedDetail>
      </ExactDetail>}
      {detail.kind === "executions" && <ExecutionDrawerContent models={models} executionId={detail.id ?? ""}
        onSelect={(id, title) => open({ kind: "executions", id, title })} />}
      {detail.kind === "evidence" && <ExactDetail requestedId={detail.id} selectedId={models.evidence.selected?.snapshot.id} busy={models.evidence.busy || models.evidence.detailBusy} error={models.evidence.error || models.evidence.detailError}>
        <GitEvidence model={models.evidence} />
      </ExactDetail>}
      {detail.kind === "policy" && <ReviewPolicy model={models.reviewPolicy} />}
      {detail.kind === "tracking" && <GithubReconciliation model={models.reconciliation} />}
      {detail.kind === "budgets" && <ExecutionBudgets model={models.budgets} />}
      {detail.kind === "formal" && <FormalVerification model={models.formalVerification} currentAcceptedHead={currentAcceptedHead} />}
      {detail.kind === "content" && <ContentChanges model={models.contentChanges} requestedId={detail.id} currentAcceptedHead={currentAcceptedHead} review={models.proposalReview?.content} />}
      {detail.kind === "acceptance-policy" && <AcceptancePolicy model={models.proposalReview?.policy} />}
      {detail.kind === "api" && <AgentApi project={models.executions.project} workspace={models.executions.workspace} />}
      {detail.kind === "history" && <div className="oporahub-workspace__body">
        <GraphProposals model={models.graphProposals} review={models.proposalReview?.graph} /><PlanChanges model={models.changes} review={models.proposalReview?.spec} acceptancePolicy={models.proposalReview?.policy} />
        <ProposalHistory model={models.proposals} /><SyncDashboard view={models.view} onRefresh={models.onRefresh} />
      </div>}
    </OverviewDrawer>}
  </section>;
}
