import { BaseEdge, Position, type Edge, type EdgeProps } from "@xyflow/react";
import { studioBezier, type PortSide } from "@/project/studio/studio-canvas/logic/studio-bezier";
import StudioLinkMotion from "@/project/studio/studio-motion/components/StudioLinkMotion";
import type { LinkMotion } from "@/project/studio/studio-motion/logic/motion-plan";
import "../styles/map-link.css";

export type MapLinkData = {
  /** Barva tahu vazby (token druhu toku nebo barva zdroje): nese ji i tečka pohybu. */
  tone: string;
  /** Pohyb Skutečnosti na této vazbě; chybí = vazba stojí. */
  motion?: LinkMotion;
};
export type MapLinkEdge = Edge<MapLinkData, "map-link">;

const SIDE: Record<Position, PortSide> = { [Position.Left]: "left", [Position.Right]: "right", [Position.Top]: "top", [Position.Bottom]: "bottom" };

/** Vazba mapy jako ve Studiu: Bézierova křivka z výstupního portu do vstupního (ohyb podle prototypu), barva, šířka a
 * čárkování podle `carries` (`edgeLook`, styl od plátna), šipka a popisek „pravidlo“. Široká neviditelná stopa nese
 * najetí myší (popisek vazby u kurzoru). Nad čarou leží pohyb Skutečnosti (`StudioLinkMotion`), který kreslí jeden
 * animátor plátna. */
export default function ArchitectureLink({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, style, markerEnd, label }: EdgeProps<MapLinkEdge>) {
  const { d, label: mid } = studioBezier({ x: sourceX, y: sourceY, side: SIDE[sourcePosition] }, { x: targetX, y: targetY, side: SIDE[targetPosition] });
  return <g className="map-link" style={{ ["--studio-link" as string]: data?.tone }}>
    <BaseEdge id={id} path={d} style={style} markerEnd={markerEnd} interactionWidth={18} className="map-link__line"
      label={label} labelX={mid.x} labelY={mid.y} labelStyle={{ fill: "var(--studio-text)", fontSize: 10, fontWeight: 600 }}
      labelBgStyle={{ fill: "var(--studio-bg)" }} labelBgPadding={[4, 2]} labelBgBorderRadius={4}/>
    <StudioLinkMotion d={d} mid={mid} motion={data?.motion}/>
  </g>;
}
