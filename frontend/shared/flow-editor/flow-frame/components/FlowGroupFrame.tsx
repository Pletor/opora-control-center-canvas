import { useContext } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { FlowGroupNode } from "../../logic/frame-view";
import { handleId } from "../../logic/flow-view";
import { FrameActionsContext } from "../logic/frame-actions";
import "../styles/flow-frame.css";

/** Rámec skupiny (n8n Canvas Groups): rozbalený je rám za uzly s titulkem a popisem nahoře, sbalený jeden uzel s počtem
 * kroků, do kterého vedou vazby zvenku. Chyby kontroly grafu u skupiny svítí v hlavičce červeně. Klik vybere rámec
 * (inspektor rámce), šipka ho sbalí nebo rozbalí. */
export default function FlowGroupFrame({ data }: NodeProps<FlowGroupNode>) {
  const { group, errors, collapsed, selected } = data;
  const { onToggleGroup } = useContext(FrameActionsContext);
  const state = `${collapsed ? " flow-frame__group--collapsed" : ""}${errors.length ? " flow-frame__group--invalid" : ""}${selected ? " flow-frame__group--selected" : ""}`;
  const toggle = <button type="button" className="flow-frame__toggle nodrag" data-testid={`flow-group-toggle-${group.id}`}
    aria-label={collapsed ? `Rozbalit rámec ${group.name}` : `Sbalit rámec ${group.name}`} onClick={(event) => { event.stopPropagation(); onToggleGroup(group.id); }}>{collapsed ? "▸" : "▾"}</button>;
  return <div className={`flow-frame__group${state}`} data-testid={`flow-group-${group.id}`} title={errors.join("\n") || group.description}>
    <header className="flow-frame__group-head">
      {toggle}
      <b className="flow-frame__group-name">{group.name}</b>
      {errors.length > 0 && <span className="flow-frame__group-errors" data-testid={`flow-group-errors-${group.id}`}>{errors.length} {errors.length === 1 ? "chyba" : "chyby"}</span>}
    </header>
    {group.description && <p className="flow-frame__group-description">{group.description}</p>}
    {collapsed && <>
      <p className="flow-frame__group-count">{group.nodeIds.length} kroků uvnitř</p>
      <Handle id={handleId("in", "main")} type="target" position={Position.Left} className="flow-frame__port" isConnectable={false}/>
      <Handle id={handleId("out", "main")} type="source" position={Position.Right} className="flow-frame__port" isConnectable={false}/>
    </>}
  </div>;
}
