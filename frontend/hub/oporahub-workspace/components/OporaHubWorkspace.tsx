import { useEffect, useMemo, useState } from "react";
import { acceptedPlan } from "@/hub/oporahub-overview/logic/overview";
import OporaHubOverview, { type HubTab } from "@/hub/oporahub-overview/components/OporaHubOverview";
import OverviewDrawer from "@/hub/oporahub-overview/components/OverviewDrawer";
import { openCardDrawer } from "@/hub/oporahub-card-drawer/open";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import type { OverviewModels } from "@/hub/oporahub-overview/logic/models";
import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import { initialHubLink, defaultCard } from "../logic/hub-link";
import { scopedProposalLink } from "@/hub/graph-proposals/logic/proposal-preview";
import DetailContent from "./DetailContent";
import ProcessObservatory from "@/hub/process-observatory/components/ProcessObservatory";
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
  // Jména karet pro Živý proces; klíč drží stejný objekt, dokud se jména v grafu nezmění.
  const nameKey = JSON.stringify(models.executions.choices.map(node => [node.id, node.name]));
  const names = useMemo(() => Object.fromEntries(JSON.parse(nameKey) as [string, string][]), [nameKey]);
  const [selection, setSelection] = useState<{ scope: string; target: DetailTarget } | null>(() => {
    const id = scopedProposalLink(typeof location === "undefined" ? "" : location.search, project, workspace);
    return id ? { scope, target: { kind: "graph", id, title: "Uložený návrh plánu" } } : null;
  });
  const detail = selection?.scope === scope ? selection.target : null;
  useEffect(() => {
    const id = scopedProposalLink(location.search, project, workspace);
    if (id) setSelection({ scope, target: { kind: "graph", id, title: "Uložený návrh plánu" } });
    else {
      const params = new URLSearchParams(location.search);
      if (params.get("project") === project && params.get("workspace") === workspace) {
        const changeset = params.get("ohChangeset"), baseline = params.get("ohBaseline");
        if (changeset || baseline) setSelection({ scope, target: { kind: "changes", ...(changeset ? { id: changeset } : {}), title: "Uložený návrh zadání" } });
      }
    }
  }, [scope, project, workspace]);
  const onDetailOpenChange = models.onDetailOpenChange;
  useEffect(() => { onDetailOpenChange?.(!!detail); }, [!!detail, onDetailOpenChange]);
  useEffect(() => {
    const id = models.contentChanges?.selectedId;
    if (detail?.kind === "content" && detail.id && id && id !== detail.id && models.contentChanges?.detail?.proposal.id === id)
      setSelection({ scope, target: { kind: "content", id, title: "Změny obsahu · nový návrh" } });
  }, [scope, detail, models.contentChanges?.selectedId, models.contentChanges?.detail?.proposal.id]);
  function open(target: DetailTarget) {
    const url = new URL(location.href);
    if (target.kind === "graph" && target.id) {
      url.searchParams.set("ohGraph", target.id); url.searchParams.set("project", project); url.searchParams.set("workspace", workspace);
    } else url.searchParams.delete("ohGraph");
    if (target.kind === "changes" && target.id) url.searchParams.set("ohChangeset", target.id);
    else url.searchParams.delete("ohChangeset");
    url.searchParams.delete("ohBaseline");
    history.replaceState(history.state, "", url);
    if (target.id) {
      if (target.kind === "graph") models.graphProposals.inspect(target.id);
      if (target.kind === "changes") models.changes.inspect(target.id);
      if (target.kind === "executions") models.executions.selectExecution(target.id);
      if (target.kind === "evidence") models.evidence.select(target.id);
      if (target.kind === "formal") models.formalVerification.select(target.id);
      if (target.kind === "content") models.contentChanges?.select(target.id);
    }
    if (target.kind === "content" && !target.id) models.contentChanges?.cancel();
    // Karta má jediný detail v celé aplikaci (hub/oporahub-card-drawer); OporaHub ho jen otevře.
    if (target.kind === "card") { const card = target.id || defaultCard(agent.state, models.executions.choices); if (card) openCardDrawer(card); return; }
    setSelection({ scope, target });
  }
  function close() { const url = new URL(location.href); for (const key of ["ohGraph", "ohChangeset", "ohBaseline"]) url.searchParams.delete(key); history.replaceState(history.state, "", url);
    models.proposalReview?.reset(); models.contentChanges?.cancel(); models.budgets.cancel(); models.executions.dismissCancel(); models.reviewPolicy.cancel(); models.reconciliation.cancel(); models.graphProposals.acknowledge(false); setSelection(null); }
  function refresh() {
    agent.refresh(); models.graphProposals.refresh(); models.changes.refresh(); models.executions.refresh(); models.executionObservations?.refresh();
    models.evidence.refresh(); models.reconciliation.refresh(); models.reviewPolicy.refresh(); models.formalVerification.refresh(); models.onRefresh();
  }
  return <section className="oporahub-workspace" aria-label="OporaHub" data-testid="oporahub-workspace">
    <OporaHubOverview agent={agent} tab={tab} onTab={setTab} open={open} onRefresh={refresh}
      onOpenCard={() => open({ kind: "card", title: "Detail karty" })}
      process={tab === "process" && <ProcessObservatory project={project} workspace={workspace} state={agent.state} refreshAgentState={agent.refresh} names={names} />} />
    {detail && <OverviewDrawer title={detail.title} onClose={close}>
      <DetailContent models={models} detail={detail} open={open} currentAcceptedHead={currentAcceptedHead} onChanged={agent.refresh} />
    </OverviewDrawer>}
  </section>;
}
