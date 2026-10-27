import { EdgeLabelRenderer, Position, type EdgeProps } from "@xyflow/react";
import type { StudioLinkEdge } from "../logic/canvas-flow";
import { studioBezier, type PortSide } from "../logic/studio-bezier";
import StudioLinkMotion from "../../studio-motion/components/StudioLinkMotion";

const SIDE: Record<Position, PortSide> = { [Position.Left]: "left", [Position.Right]: "right", [Position.Top]: "top", [Position.Bottom]: "bottom" };

/** Souhrnná vazba úrovně: Bézierova křivka z výstupního portu do vstupního (ohyb podle prototypu), barva a čára podle
 * převládajícího `carries`, druh a počet v tooltipu. Vazba, která shrnuje víc hran, nese uprostřed štítek s počtem
 * (při selhání cesty pod tečkou s křížkem). Nad čarou leží pohyb Skutečnosti (`StudioLinkMotion`). */
export default function StudioLink({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data }: EdgeProps<StudioLinkEdge>) {
  const { d, label } = studioBezier({ x: sourceX, y: sourceY, side: SIDE[sourcePosition] }, { x: targetX, y: targetY, side: SIDE[targetPosition] });
  const carries = data?.carries ?? "unspecified";
  return <g className={"studio-canvas__link studio-canvas__link--" + carries} data-testid={"studio-link-" + id}>
    <title>{data?.title}</title>
    <path className="studio-canvas__link-hit" d={d}/>
    <path className="studio-canvas__link-line" d={d}/>
    <StudioLinkMotion d={d} mid={label} motion={data?.motion}/>
    {data && data.count > 1 && <EdgeLabelRenderer>
      <span className={"studio-canvas__link-count studio-canvas__link-count--" + carries} title={data.title}
        style={{ transform: `translate(-50%, -50%) translate(${label.x}px, ${label.y + (data.motion?.failure ? 16 : 0)}px)` }}>{data.count}</span>
    </EdgeLabelRenderer>}
  </g>;
}
