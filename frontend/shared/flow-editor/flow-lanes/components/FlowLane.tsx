import type { NodeProps } from "@xyflow/react";
import type { FlowLaneNode } from "../logic/lanes";
import { LAYER_LABEL } from "../logic/layers";
import "../styles/flow-lanes.css";

/** Pruh jedné vrstvy za uzly: barevné pozadí s názvem vrstvy v levém horním rohu. Jen zobrazení, na kliknutí nereaguje. */
export default function FlowLane({ data }: NodeProps<FlowLaneNode>) {
  return <div className={`flow-lanes__lane flow-lanes__lane--${data.layer}`} data-testid={`flow-lane-${data.layer}`}>
    <span className="flow-lanes__name">{LAYER_LABEL[data.layer]}</span>
  </div>;
}
