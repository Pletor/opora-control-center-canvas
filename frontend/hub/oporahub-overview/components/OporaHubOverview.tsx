import type { ReactNode } from "react";
import { mirrorJson } from "@/hub/oporahub-agent-state/logic/agent-state";
import type { AgentStateView } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import LoopOverview from "@/hub/oporahub-loop/components/LoopOverview";
import AgentsView from "@/hub/oporahub-agents/components/AgentsView";
import type { DetailTarget } from "../logic/overview";
import LegacyLinks from "./LegacyLinks";
import "../styles/oporahub-overview.css";

export type HubTab = "overview" | "process" | "agents";
type Props = {
  agent: Pick<AgentStateView, "state" | "etag" | "error" | "loadedAt">; tab: HubTab; onTab: (tab: HubTab) => void;
  onOpenCard: () => void; open: (target: DetailTarget) => void; onRefresh: () => void;
  /** Záložka „Živý proces“ (hub/process-observatory); skládá ji prostředí, jen když je záložka otevřená. */
  process?: ReactNode;
};
const freshness = (loadedAt: number, generatedAt?: string) => {
  if (!loadedAt) return "načítám…";
  const time = generatedAt ? Date.parse(generatedAt) : NaN;
  return `snímek ${Number.isFinite(time) ? new Date(time).toLocaleTimeString("cs-CZ") : "?"}`;
};

/** Jedna stránka OporaHubu: záložky, jeden dokument agent-state, jeho zrcadlo v DOM a odkazy na původní formuláře. */
export default function OporaHubOverview({ agent, tab, onTab, onOpenCard, open, onRefresh, process }: Props) {
  const state = agent.state;
  return <div className="oporahub-overview" data-oh-view={tab === "agents" ? "agent" : tab} data-oh-schema-version="1"
    data-oh-accepted-head={state?.heads.acceptedHead ?? ""} data-oh-etag={agent.etag} data-oh-generated-at={state?.generatedAt ?? ""}>
    <script type="application/json" id="oh-agent-state" dangerouslySetInnerHTML={{ __html: mirrorJson(state) }} />
    <header className="oporahub-overview__top">
      <h1 className="oporahub-overview__brand">OporaHub</h1>
      <span className="oporahub-overview__crumb">projekt <b>{state?.projectId ?? "—"}</b> · prostor <b>{state?.workspaceId ?? "—"}</b> · {freshness(agent.loadedAt, state?.generatedAt)}</span>
      <nav className="oporahub-overview__tabs" aria-label="Pohled OporaHubu">
        <button type="button" className="oporahub-overview__tab" aria-pressed={tab === "overview"} onClick={() => onTab("overview")}>Přehled</button>
        <button type="button" className="oporahub-overview__tab" aria-pressed={tab === "process"} onClick={() => onTab("process")}>Živý proces</button>
        <button type="button" className="oporahub-overview__tab" aria-pressed={false} onClick={onOpenCard}>Karta</button>
        <button type="button" className="oporahub-overview__tab" aria-pressed={tab === "agents"} onClick={() => onTab("agents")}>Pro agenty</button>
      </nav>
    </header>
    {agent.error && <p className="oporahub-overview__warning" role="status">{agent.error}{state ? " Zobrazený snímek může být neaktuální." : ""}</p>}
    {!state && !agent.error && tab !== "process" && <p className="oporahub-overview__empty" role="status">Načítám stav OporaHubu…</p>}
    {tab === "process" ? process : state && (tab === "agents" ? <AgentsView state={state} open={open} /> : <LoopOverview state={state} open={open} />)}
    <LegacyLinks open={open} onRefresh={onRefresh} />
  </div>;
}
