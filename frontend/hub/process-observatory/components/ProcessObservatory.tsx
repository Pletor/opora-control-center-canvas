import { useMemo, useState } from "react";
import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";
import { openCardDrawer } from "@/hub/oporahub-card-drawer/open";
import FlowMap from "../flow-map/components/FlowMap";
import EventStream from "../event-stream/components/EventStream";
import CardInspector from "../card-inspector/components/CardInspector";
import { buildLanes, type CardSnapshot } from "../logic/lanes";
import { ago } from "../logic/process-event";
import { sourceChips } from "../logic/source-health";
import { visibleStream, workerOptions } from "../logic/stream-buffer";
import { useProcessHealth } from "../logic/use-process-health";
import { useProcessStream } from "../logic/use-process-stream";
import SourceHealth from "./SourceHealth";
import BlockersStrip from "./BlockersStrip";
import "../styles/process-observatory.css";

type Props = {
  project: string; workspace: string; state: AgentState | null; refreshAgentState: () => void;
  /** Jména karet z grafu (`nodeId` → název); karta bez jména ukáže své id. */
  names: Record<string, string>;
};

/**
 * Záložka „Živý proces“: zdroje, blokace, mapa toku, proud událostí a inspektor. Mountuje se jen s otevřenou
 * záložkou v OporaHubu, takže odběr toku i čtení zdraví běží jen tehdy.
 */
export default function ProcessObservatory({ project, workspace, state, refreshAgentState, names }: Props) {
  const stream = useProcessStream(project, workspace, refreshAgentState);
  const health = useProcessHealth(project, workspace);
  const [picked, setPicked] = useState<string | null>(null);
  const [filter, setFilter] = useState({ card: "", worker: "" });
  const officeConnected = health.health ? health.health.officeConnected : null;
  const cards = (state?.cards ?? []) as CardSnapshot[];
  const lanes = useMemo(() => buildLanes(cards, stream.events, { names, officeConnected }), [cards, stream.events, names, officeConnected]);
  const now = Date.now();
  const selected = lanes.find((lane) => lane.nodeId === picked) ?? lanes[0] ?? null;
  const office = health.health?.sources.office;
  const officeSilence = officeConnected === false && office?.lastAt ? ago(Date.parse(office.lastAt), now) : null;
  const rows = visibleStream(stream.buffer.shown, filter);
  return <div className="process-observatory" data-oh-view="process">
    <SourceHealth chips={sourceChips(health.health)} transport={stream.transport} error={stream.error || health.error} />
    <BlockersStrip lanes={lanes} now={now} onSelect={setPicked} />
    <div className="process-observatory__main">
      <FlowMap lanes={lanes} selected={selected?.nodeId ?? null} now={now} onSelect={setPicked} officeSilence={officeSilence} />
      <CardInspector lane={selected} onOpenCard={(nodeId, tab) => openCardDrawer(nodeId, tab)} />
      <EventStream rows={rows} total={stream.buffer.shown.length} paused={stream.buffer.paused} buffered={stream.buffer.pending.length}
        anyEvent={stream.events.length > 0} cards={lanes.map((lane) => ({ id: lane.nodeId, name: lane.title }))}
        workers={workerOptions(stream.events)} card={filter.card} worker={filter.worker}
        onCard={(card) => setFilter((current) => ({ ...current, card }))} onWorker={(worker) => setFilter((current) => ({ ...current, worker }))}
        onTogglePause={stream.togglePause} />
    </div>
  </div>;
}
