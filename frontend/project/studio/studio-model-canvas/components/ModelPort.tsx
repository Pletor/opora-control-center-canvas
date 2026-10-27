import type { PointerEvent } from "react";
import type { PortView } from "../logic/model-flow";

/** Port na obvodu karty: průhledná trefovací plocha s barevnou tečkou uprostřed (barva = datový typ). Vybraný port
 * svítí, kompatibilní cíl zeleně, nekompatibilní je ztlumený. Myš hlásí stisk (`onDown`: klik nebo tah), klávesnice
 * Enter / mezerník (`onKey`). Klik nebublá do karty, aby výběr portu nevybral i kartu. */
export default function ModelPort({ nodeId, nodeName, port, onDown, onKey }: { nodeId: string; nodeName: string; port: PortView; onDown: (event: PointerEvent) => void; onKey: () => void }) {
  const state = port.pending ? " studio-model-canvas__port--pending" : port.target ? " studio-model-canvas__port--" + port.target : "";
  const label = `${port.direction === "input" ? "IN" : "OUT"} · ${port.id} · ${port.type} · ${port.connected} připojeno`;
  return <button type="button" className={`studio-model-canvas__port studio-model-canvas__port--${port.side} nodrag nopan${state}`}
    style={{ left: port.x, top: port.y, ["--studio-port" as string]: port.color }} title={label} aria-label={`${nodeName}: ${label}`} aria-pressed={port.pending}
    data-port-node={nodeId} data-port-id={port.id} data-port-direction={port.direction} data-testid={`studio-model-port-${nodeId}-${port.id}`}
    onPointerDown={onDown} onClick={(event) => { event.stopPropagation(); if (event.detail === 0) onKey(); }}>
    <span className={"studio-model-canvas__port-dot" + (port.connected ? " studio-model-canvas__port-dot--connected" : "")} aria-hidden="true"/>
  </button>;
}
