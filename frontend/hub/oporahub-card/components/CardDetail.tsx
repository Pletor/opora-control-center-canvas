import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";
import type { BudgetContext } from "@/hub/execution-budgets/logic/execution-budgets";
import type { ExecutionSummary } from "@/hub/execution-receipts/logic/execution-receipts";
import type { PlanChangeset } from "@/hub/plan-changes/logic/plan-changes";
import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import { cardTimeline, type TimelineStep } from "../logic/card-timeline";
import { ToneChip } from "@/hub/oporahub-health/components/HealthMark";
import CardTimeline from "./CardTimeline";
import { CardApprovals, CardBudget, CardEvidence } from "./CardPanels";
import CardReviewGate from "@/hub/oporahub-review-gate/components/CardReviewGate";
import CardProofs from "@/hub/oporahub-proofs/components/CardProofs";
import CardHistory from "@/hub/oporahub-card-history/components/CardHistory";
import "../styles/oporahub-card.css";

type Props = {
  project: string; workspace: string; nodeId: string; cards: { id: string; name: string }[]; state: AgentState | null; changesets: PlanChangeset[];
  executions: ExecutionSummary[]; budget: BudgetContext | null; busy: boolean;
  onSelect: (nodeId: string) => void; open: (target: DetailTarget) => void;
};

/** Detail karty: kdo s kartou co dělal, na jaké revizi, a co ji dělí od zápisu zpět do plánu. */
export default function CardDetail({ project, workspace, nodeId, cards, state, changesets, executions, budget, busy, onSelect, open }: Props) {
  const view = cardTimeline({ nodeId, state, changesets, executions });
  const name = cards.find(item => item.id === nodeId)?.name ?? nodeId;
  const mine = changesets.filter(item => item.changes.some(change => change.nodeId === nodeId));
  function openStep(step: TimelineStep) {
    if (step.kind === "changeset") open({ kind: "changes", id: step.id, title: `Návrh zadání · ${name}` });
    else if (view.latest) open({ kind: "executions", id: view.latest.executionId, title: `Běh · ${name}` });
    else open({ kind: "budgets", title: `Pravidla běhů · ${name}` });
  }
  return <div className="oporahub-card" data-oh-view="card" data-oh-node-id={nodeId} data-oh-accepted-head={state?.heads.acceptedHead ?? ""}>
    <header className="oporahub-card__head">
      <div className="oporahub-card__head-main">
        <h2 className="oporahub-card__name">{name}</h2><code className="oporahub-card__note">{nodeId}</code>
        {view.latest && <ToneChip tone="acc">{view.latest.state} · {view.latest.executionId.slice(0, 8)}</ToneChip>}
        {busy && <span className="oporahub-card__note" role="status">Načítám historii karty…</span>}
      </div>
      <div className="oporahub-card__actions">
        <label className="oporahub-card__picker">Karta
          <select value={nodeId} onChange={event => onSelect(event.target.value)}>
            {cards.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        <button type="button" className="oporahub-card__ghost" onClick={() => open({ kind: "changes", title: `Navrhnout změnu · ${name}` })}>Navrhnout změnu</button>
      </div>
    </header>
    <CardTimeline steps={view.steps} forks={view.forks} onOpen={openStep} />
    <div className="oporahub-card__bottom">
      <CardBudget budget={budget?.nodeId === nodeId ? budget : null} latest={view.latest} claim={view.claim} />
      <CardApprovals changesets={mine} />
      <CardEvidence latest={view.latest} gaps={state?.gaps ?? []} />
    </div>
    <div className="oporahub-card__more">
      <CardReviewGate project={project} workspace={workspace} nodeId={nodeId} state={state} />
      <CardProofs project={project} workspace={workspace} nodeId={nodeId} state={state} onOpenLedger={() => open({ kind: "proof-ledger", title: "Kniha důkazů" })} />
    </div>
    <CardHistory project={project} workspace={workspace} nodeId={nodeId} />
  </div>;
}
