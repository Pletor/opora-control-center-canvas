import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";
import { loopModel } from "@/hub/oporahub-agent-state/logic/loop-model";
import { stripModel } from "@/hub/oporahub-agent-state/logic/strip-model";
import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import HealthMark, { ToneChip } from "@/hub/oporahub-health/components/HealthMark";
import TopStrip from "./TopStrip";
import StageNode from "./StageNode";
import LoopConnector from "./LoopConnector";
import "../styles/oporahub-loop.css";

/** Přehled: horní pás, smyčka deseti etap plán → kód → plán a pás známých mezer. */
export default function LoopOverview({ state, open }: { state: AgentState; open: (target: DetailTarget) => void }) {
  const strip = stripModel(state);
  return <div className="oporahub-loop">
    <TopStrip strip={strip} open={open} />
    <section className="oporahub-loop__panel" aria-label="Životní cyklus plánu">
      <header className="oporahub-loop__panel-head"><h2 className="oporahub-loop__title">Smyčka plán → kód → plán</h2>
        <span className="oporahub-loop__sub">{state.truncated ? "projekce karet narazila na limit 100" : "počty ze serverového snímku"}</span></header>
      <div className="oporahub-loop__grid">
        {loopModel(state).map(item => item.kind === "stage"
          ? <StageNode key={item.stage.id} stage={item.stage} onOpen={() => open(item.stage.target)} />
          : <LoopConnector key={`${item.connector.from}-link`} connector={item.connector} />)}
      </div>
      <footer className="oporahub-loop__foot">
        <span className="oporahub-loop__legend">
          <HealthMark health="ok" /><HealthMark health="waiting" text="čeká / pozor" /><HealthMark health="blocking" /><HealthMark health="not_connected" text="zatím nenapojeno" />
        </span>
        <span className="oporahub-loop__gaps" data-oh-list="gaps">
          <span className="oporahub-loop__label">Známé mezery</span>
          {strip.gaps.map(item => <span key={item.id} title={item.reason} data-oh-gap={item.id} data-oh-health="not_connected"><ToneChip tone="gap">◌ {item.label}</ToneChip></span>)}
        </span>
      </footer>
    </section>
  </div>;
}
