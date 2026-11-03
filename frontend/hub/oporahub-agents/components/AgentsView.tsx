import { agentStateEndpoint, type AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";
import { actionRows, headFacts, PROTOCOL, type ActionRow } from "@/hub/oporahub-agent-state/logic/actions-model";
import { actionTarget } from "@/hub/oporahub-agent-state/logic/action-target";
import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import ActionQueue from "./ActionQueue";
import StateJson from "./StateJson";
import ContractTable from "./ContractTable";
import "../styles/oporahub-agents.css";

/** Pohled pro agenty: protokol, hlavy pro CAS, fronta akcí, přesný JSON a kontrakt data-oh. */
export default function AgentsView({ state, open }: { state: AgentState; open: (target: DetailTarget) => void }) {
  const rows = actionRows(state);
  const openTarget = (row: ActionRow) => open(actionTarget(row, `${row.verbLabel} · ${row.targetId ?? ""}`));
  return <div className="oporahub-agents">
    <ol className="oporahub-agents__protocol" aria-label="Protokol">
      <li className="oporahub-agents__protocol-step oporahub-agents__protocol-step--lead">PROTOKOL</li>
      {PROTOCOL.map(step => <li key={step} className="oporahub-agents__protocol-step">{step}</li>)}
    </ol>
    <dl className="oporahub-agents__facts" data-oh-facts="">
      {headFacts(state).map(fact => <div key={fact.field} className="oporahub-agents__fact" data-oh-field={fact.field} data-oh-value={fact.value}>
        <dt className="oporahub-agents__fact-name">{fact.field}</dt><dd className="oporahub-agents__fact-value" title={fact.value}>{fact.value}</dd>
      </div>)}
    </dl>
    <ActionQueue rows={rows} onOpenTarget={openTarget} />
    <div className="oporahub-agents__pair">
      <StateJson endpoint={agentStateEndpoint(state.projectId, state.workspaceId)} json={JSON.stringify(state, null, 2)} />
      <ContractTable />
    </div>
  </div>;
}
