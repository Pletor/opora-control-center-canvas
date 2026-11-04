import { useContext } from "react";
import { Handle, Position } from "@xyflow/react";
import type { PortView } from "../../logic/flow-view";
import { PortActionsContext } from "../logic/port-actions";

const POSITION = { left: Position.Left, right: Position.Right, bottom: Position.Bottom, top: Position.Top } as const;

/** Port uzlu: kruh pro hlavní tok, kosočtverec pro sub-port. Popisek stojí u portu (povinný má hvězdičku) a sub-vstup,
 * který ještě unese vazbu (prázdný, nebo s více vazbami jako Nástroj), či volný výstup nabídne „+“, které otevře paletu
 * jen s kompatibilními typy. Plný port s jedinou vazbou „+“ nemá. */
export default function FlowPort({ nodeId, port, readOnly }: { nodeId: string; port: PortView; readOnly: boolean }) {
  const { onPlus } = useContext(PortActionsContext);
  const vertical = port.side === "bottom" || port.side === "top";
  const place = vertical ? { left: `${port.offset * 100}%` } : { top: `${port.offset * 100}%` };
  const sub = port.kind !== "main";
  const free = !port.connected || (sub && port.cardinality === "many");
  const showPlus = !readOnly && free && ((sub && port.direction === "in") || (!sub && port.direction === "out"));
  const missing = port.required && !port.connected;
  return <>
    <Handle id={port.handleId} type={port.direction === "in" ? "target" : "source"} position={POSITION[port.side]} style={place}
      className={`flow-node__port flow-node__port--${port.side}${sub ? " flow-node__port--sub" : ""}${missing ? " flow-node__port--missing" : ""}`}
      title={`${port.direction === "in" ? "vstup" : "výstup"} ${port.name} · ${port.kind} · ${port.cardinality === "one" ? "jedna vazba" : "více vazeb"}`}/>
    {port.label && <span className={`flow-node__port-label flow-node__port-label--${port.side}`} style={place}>
      {port.label}{port.required && <b className="flow-node__required">*</b>}</span>}
    {showPlus && <button type="button" className={`flow-node__plus flow-node__plus--${port.side}${port.label && port.side === "right" ? " flow-node__plus--labelled" : ""} nodrag nopan`} style={place}
      aria-label={`Přidat uzel k portu ${port.name}`} data-testid={`flow-plus-${nodeId}-${port.name}`}
      onClick={(event) => { event.stopPropagation(); onPlus({ nodeId, port: port.name, direction: port.direction, kind: port.kind }); }}>+</button>}
  </>;
}
