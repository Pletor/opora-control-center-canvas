import { useEffect, useState } from "react";
import { acceptedPlan } from "@/hub/oporahub-overview/logic/overview";
import OporaHubOverview, { type HubTab } from "@/hub/oporahub-overview/components/OporaHubOverview";
import OverviewDrawer from "@/hub/oporahub-overview/components/OverviewDrawer";
import CardDetail from "@/hub/oporahub-card/components/CardDetail";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import type { OverviewModels } from "@/hub/oporahub-overview/logic/models";
import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import { initialHubLink, defaultCard } from "../logic/hub-link";
import DetailContent from "./DetailContent";
import "@/hub/oporahub-workspace/styles/oporahub-workspace.css";

export { ExecutionDrawerContent } from "./DetailContent";

// App vlastní data a mutace. Prostředí čte jediný dokument agent-state a skládá dílky;
// starší hooky se probouzejí až s otevřeným detailem (onDetailOpenChange).
export default function OporaHubWorkspace(models: OverviewModels) {
  const project = models.executions.project ?? "", workspace = models.executions.workspace ?? "";
  const agent = useAgentState(project, workspace);
  const plan = acceptedPlan(models.graphProposals.context, models.changes.context);
  const currentAcceptedHead = !models.graphProposals.busy && !models.changes.busy && !models.graphProposals.error && !models.changes.error && plan.basisKnown ? plan.head : null;
  const scope = JSON.stringify([project, workspace]);
  const [link] = useState(() => initialHubLink(typeof location === "undefined" ? "" : location.search));
  const [tab, setTab] = useState<HubTab>(link.tab);
  const [selection, setSelection] = useState<{ scope: string; target: DetailTarget } | null>(() => link.card ? { scope, target: { kind: "card", id: link.card, title: "Detail karty" } } : null);
  const detail = selection?.scope === scope ? selection.target : null;
  const onDetailOpenChange = models.onDetailOpenChange;
  useEffect(() => { onDetailOpenChange?.(!!detail); }, [!!detail, onDetailOpenChange]);
  useEffect(() => {
    const id = models.contentChanges?.selectedId;
    if (detail?.kind === "content" && detail.id && id && id !== detail.id && models.contentChanges?.detail?.proposal.id === id)
      setSelection({ scope, target: { kind: "content", id, title: "Změny obsahu · nový návrh" } });
  }, [scope, detail, models.contentChanges?.selectedId, models.contentChanges?.detail?.proposal.id]);
  useEffect(() => { if (detail?.kind === "card" && detail.id) models.budgets.select(detail.id); }, [detail?.kind, detail?.id]);
  const cardRequest = models.cardRequest;
  useEffect(() => { if (cardRequest?.id) setSelection({ scope, target: { kind: "card", id: cardRequest.id, title: "Detail karty" } }); }, [cardRequest?.nonce]);
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
    const card = target.kind === "card" ? target.id || defaultCard(agent.state, models.executions.choices) : "";
    if (target.kind === "card" && !card) return;
    setSelection({ scope, target: target.kind === "card" ? { ...target, id: card } : target });
  }
  function close() { models.proposalReview?.reset(); models.contentChanges?.cancel(); models.budgets.cancel(); models.executions.dismissCancel(); models.reviewPolicy.cancel(); models.reconciliation.cancel(); models.graphProposals.acknowledge(false); setSelection(null); }
  function refresh() {
    agent.refresh(); models.graphProposals.refresh(); models.changes.refresh(); models.executions.refresh(); models.executionObservations?.refresh();
    models.evidence.refresh(); models.reconciliation.refresh(); models.reviewPolicy.refresh(); models.formalVerification.refresh(); models.onRefresh();
  }
  const cards = models.executions.choices.map(item => ({ id: item.id, name: item.name }));
  return <section className="oporahub-workspace" aria-label="OporaHub" data-testid="oporahub-workspace">
    <OporaHubOverview agent={agent} tab={tab} onTab={setTab} open={open} onRefresh={refresh}
      onOpenCard={() => open({ kind: "card", title: "Detail karty" })} />
    {detail && <OverviewDrawer title={detail.kind === "card" ? `Karta · ${cards.find(item => item.id === detail.id)?.name ?? detail.id}` : detail.title} onClose={close} wide={detail.kind === "card"}>
      {detail.kind === "card" && detail.id ? <CardDetail project={project} workspace={workspace} nodeId={detail.id} cards={cards} state={agent.state} changesets={models.changes.items}
        executions={models.executions.executions} budget={models.budgets.context} busy={models.changes.busy || models.executions.busy}
        onSelect={id => open({ kind: "card", id, title: "Detail karty" })} open={open} />
        : <DetailContent models={models} detail={detail} open={open} currentAcceptedHead={currentAcceptedHead} onChanged={agent.refresh} />}
    </OverviewDrawer>}
  </section>;
}
