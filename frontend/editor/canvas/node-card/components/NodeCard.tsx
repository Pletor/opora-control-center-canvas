// Rodič karty: skládá hlavu, tělo, bloky obsahu, patu a porty. Děti nic nevědí o plátně ani o stavu; události
// (přejmenování, změna bloku, port bloku, klik na port, klik na štítek) bublají sem a odsud do dat React Flow uzlu.
import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import CardHead from "@/editor/canvas/node-card/components/CardHead";
import CardBody, { type RenameHandlers } from "@/editor/canvas/node-card/components/CardBody";
import CardBlocks, { type CardBlockHandlers } from "@/editor/canvas/node-card/components/CardBlocks";
import CardFoot from "@/editor/canvas/node-card/components/CardFoot";
import CardPorts, { type BlockPort } from "@/editor/canvas/node-card/components/CardPorts";
import type { CardView } from "@/editor/canvas/node-card/logic/card-model";
import "@/editor/canvas/node-card/styles/node-card.css";

export type NodeCardData = {
  view: CardView;
  rename: RenameHandlers;
  ports: { open: BlockPort[]; toggle: (port: BlockPort) => void };
  /** Bloky obsahu v kartě i jejich porty: přidat / posunout / odebrat / přejmenovat / upravit text; ukládá rodič (App). */
  blocks: CardBlockHandlers & { disabled: boolean };
  /** Filtr štítků: karta bez vybraného štítku je ztlumená. */
  dimmed: boolean;
  onTag: (tag: string) => void;
  /** Id bloku vybraného na plátně (jen pro vybraný uzel); zvýrazní jeho rámeček v kartě. */
  selectedBlockId?: string;
};

const NodeCard = memo(function NodeCard({ id, data, selected }: NodeProps<Node<NodeCardData>>) {
  const { view, rename, ports, blocks, dimmed, onTag, selectedBlockId } = data;
  return (
    <div
      className={
        "node-card" +
        (view.kind === "sector" ? " node-card--sector" : "") +
        (selected ? " node-card--selected" : "") +
        (dimmed ? " node-card--dimmed" : "") +
        (view.closed ? " node-card--closed" : "")
      }
      data-testid={"node-card-" + id}
    >
      <CardHead view={view} />
      <CardBody id={id} name={view.name} purpose={view.purpose} rename={rename} />
      <CardBlocks id={id} rows={view.rows} disabled={blocks.disabled} handlers={blocks} selectedBlockId={selectedBlockId} />
      <CardFoot view={view} onTag={onTag} />
      <CardPorts id={id} open={ports.open} onToggle={ports.toggle} />
    </div>
  );
});

export default NodeCard;
