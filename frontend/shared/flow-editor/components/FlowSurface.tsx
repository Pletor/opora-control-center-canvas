import type { DragEvent, HTMLAttributes, ReactNode } from "react";
import { Background, BackgroundVariant, Controls, MiniMap, ReactFlow, useReactFlow, type Edge, type Node, type NodeTypes, type OnNodesChange, type ReactFlowProps } from "@xyflow/react";
import { PALETTE_DRAG_TYPE } from "../node-palette/logic/palette";

type Point = { x: number; y: number };
type RootProps = HTMLAttributes<HTMLDivElement> & { [attribute: `data-${string}`]: string | number | undefined };

export type SurfaceView = {
  minZoom: number; maxZoom: number; fitPadding: number; dotGap: number; dotColor: string;
  controls: "top-left" | "top-right"; minimapLabel: string; minimapClass: string; controlsClass?: string; minimapNode?: string; minimapMask?: string;
};

type Props<N extends Node> = {
  nodes: N[]; edges: Edge[]; nodeTypes: NodeTypes; view: SurfaceView; rootProps: RootProps;
  onNodesChange: OnNodesChange<N>;
  /** Puštění typu z palety na plátno (souřadnice už v prostoru plátna); bez něj plátno nic nepřijímá (jen ke čtení). */
  onDropType?: (type: string, at: Point) => void;
  /** Zbytek vlastností React Flow, které se mezi editory liší (výběr, tah, klávesy). */
  flowProps?: Partial<ReactFlowProps<N>>;
  /** Uvnitř React Flow (vrstva vazeb) a nad ním (štítky, prázdný stav). */
  children?: ReactNode; overlay?: ReactNode;
};

/** Společná kostra plátna nad React Flow pro editor toků i Studio MODEL: tečkovaná mřížka, zoom, minimapa, ovládání
 * a přijetí typu puštěného z palety. Co uzel ukazuje a jak se vazby kreslí, dodává volající (`nodeTypes`, `children`).
 * Musí ležet uvnitř `ReactFlowProvider`, aby volající směl sám převádět souřadnice. */
export default function FlowSurface<N extends Node>({ nodes, edges, nodeTypes, view, rootProps, onNodesChange, onDropType, flowProps, children, overlay }: Props<N>) {
  const flow = useReactFlow();
  const drop = (event: DragEvent) => {
    const type = event.dataTransfer.getData(PALETTE_DRAG_TYPE);
    if (!type || !onDropType) return;
    event.preventDefault();
    onDropType(type, flow.screenToFlowPosition({ x: event.clientX, y: event.clientY }));
  };
  const fit = { padding: view.fitPadding, maxZoom: 1 };
  return <div {...rootProps}
    onDragOver={(event) => { if (onDropType && event.dataTransfer.types.includes(PALETTE_DRAG_TYPE)) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } }} onDrop={drop}>
    <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} fitView fitViewOptions={fit}
      minZoom={view.minZoom} maxZoom={view.maxZoom} deleteKeyCode={null} colorMode="dark" zoomOnDoubleClick={false} {...flowProps}>
      <Background variant={BackgroundVariant.Dots} gap={view.dotGap} size={1.2} color={view.dotColor}/>
      {children}
      <MiniMap position="bottom-right" pannable zoomable ariaLabel={view.minimapLabel} className={view.minimapClass} nodeBorderRadius={view.minimapNode ? 6 : 8}
        {...(view.minimapNode ? { nodeColor: () => view.minimapNode!, maskColor: view.minimapMask } : {})}/>
      <Controls position={view.controls} showInteractive={false} className={view.controlsClass} fitViewOptions={fit}/>
    </ReactFlow>
    {overlay}
  </div>;
}
