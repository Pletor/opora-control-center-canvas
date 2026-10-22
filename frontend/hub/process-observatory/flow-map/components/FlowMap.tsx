import { useRef, useState } from "react";
import { stableOrder, type Lane } from "../../logic/lanes";
import { PHASES } from "../../logic/process-event";
import FlowRow from "./FlowRow";
import "../styles/flow-map.css";

type Props = {
  lanes: Lane[]; selected: string | null; now: number; onSelect: (nodeId: string) => void;
  /** Kancelář poslala dřív něco, teď je ticho: text nad řádky (null = připojeno nebo neznámo). */
  officeSilence: string | null;
};

/** Mapa toku: hlavička sedmi fází s počty značek, řádky karet a legenda tvarů. */
export default function FlowMap({ lanes, selected, now, onSelect, officeSilence }: Props) {
  const [hover, setHover] = useState(false);
  const order = useRef<string[]>([]);
  order.current = stableOrder(order.current, lanes.map((lane) => lane.nodeId), hover);
  const byId = new Map(lanes.map((lane) => [lane.nodeId, lane]));
  const rows = order.current.map((id) => byId.get(id)).filter((lane): lane is Lane => !!lane);
  const counts = PHASES.map((_, index) => lanes.filter((lane) => lane.phase === index && lane.last).length);
  return <section className="flow-map" aria-label="Mapa toku">
    <div className="flow-map__panel-head"><h2 className="flow-map__heading">Mapa toku</h2>
      <span className="flow-map__meta">{lanes.length ? `${lanes.length} ${lanes.length === 1 ? "aktivní karta" : "aktivních karet"} · nejdřív blokace, pak poslední událost` : "0 aktivních karet"}</span></div>
    {officeSilence && <div className="flow-map__note" role="status"><i className="flow-map__note-dot" aria-hidden="true" />
      <span><b>Kancelář odpojena {officeSilence}.</b> Řádky z kanceláře ukazují poslední potvrzený stav, nic se nedomýšlí. Po obnovení se dohání od kurzoru.</span></div>}
    <div className="flow-map__head">
      <span className="flow-map__head-label">Karta · pracovník</span>
      {PHASES.map(([id, name], index) => <span key={id} className="flow-map__phase" title={id}>
        <span className="flow-map__num">{index + 1}</span><span className="flow-map__phase-name">{name}</span>
        {counts[index] > 0 && <span className="flow-map__count">{counts[index]}</span>}
      </span>)}
    </div>
    {!rows.length && <div className="flow-map__empty" role="status">
      <b className="flow-map__empty-title">Zatím žádná událost — kancelář ani Opora nic nehlásí</b>
      <span>Řádek se objeví s první událostí karty.</span>
    </div>}
    <div className="flow-map__body" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      {rows.map((lane) => <FlowRow key={lane.nodeId} lane={lane} selected={lane.nodeId === selected} now={now} onSelect={onSelect} />)}
    </div>
    <div className="flow-map__foot">
      <div className="flow-map__legend">
        <span className="flow-map__legend-item"><i className="flow-map__legend-marker" />pracovník v aktuální fázi</span>
        <span className="flow-map__legend-item"><i className="flow-map__trail flow-map__trail--ok" />potvrzeno</span>
        <span className="flow-map__legend-item"><i className="flow-map__trail flow-map__trail--fail" />selhalo</span>
        <span className="flow-map__legend-item"><i className="flow-map__trail flow-map__trail--wait" />čeká</span>
        <span className="flow-map__legend-item"><i className="flow-map__trail flow-map__trail--seen" />proběhlo bez potvrzení</span>
        <span className="flow-map__legend-item"><i className="flow-map__trail flow-map__trail--none" />bez události</span>
      </div>
      <span className="flow-map__meta">značka se hýbe jen při skutečné události</span>
    </div>
  </section>;
}
