import { useEffect, useRef, useState } from "react";
import { BaseEdge, Position, type Edge, type EdgeProps } from "@xyflow/react";
import { studioBezier, type PortSide } from "@/project/studio/studio-canvas/logic/studio-bezier";
import StudioLinkMotion from "@/project/studio/studio-motion/components/StudioLinkMotion";
import type { LinkMotion } from "@/project/studio/studio-motion/logic/motion-plan";
import LinkTrash from "./LinkTrash";
import "../styles/map-link.css";

export type MapLinkData = {
  /** Barva tahu vazby (token druhu toku nebo barva zdroje): nese ji i tečka pohybu. */
  tone: string;
  /** Pohyb Skutečnosti na této vazbě; chybí = vazba stojí. */
  motion?: LinkMotion;
  /** Popelnice: jen u nakreslené vazby (`next` / `flow`) na odemčeném plátně; chybí = vazbu odsud smazat nejde. */
  onRemove?: (edgeId: string) => void;
};
export type MapLinkEdge = Edge<MapLinkData, "map-link">;

const SIDE: Record<Position, PortSide> = { [Position.Left]: "left", [Position.Right]: "right", [Position.Top]: "top", [Position.Bottom]: "bottom" };
/** Směr, kterým vazba vychází z portu (Bézier vede chvíli rovně ven), a vzdálenost popelnice od portu. */
const OUT: Record<Position, { x: number; y: number }> = { [Position.Left]: { x: -1, y: 0 }, [Position.Right]: { x: 1, y: 0 }, [Position.Top]: { x: 0, y: -1 }, [Position.Bottom]: { x: 0, y: 1 } };
const TRASH_GAP = 26;

/** Vazba mapy jako ve Studiu: Bézierova křivka z výstupního portu do vstupního (ohyb podle prototypu), barva, šířka a
 * čárkování podle `carries` (`edgeLook`, styl od plátna), šipka a popisek „pravidlo“. Široká neviditelná stopa nese
 * najetí myší (popisek vazby u kurzoru). Nad čarou leží pohyb Skutečnosti (`StudioLinkMotion`), který kreslí jeden
 * animátor plátna. Odstranitelná vazba ukáže pod myší popelnici (`LinkTrash`) těsně za výstupním portem; krátká prodleva při odchodu nechá
 * kurzor přejít z čáry na popelnici, aniž by zmizela. */
export default function ArchitectureLink({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, style, markerEnd, label }: EdgeProps<MapLinkEdge>) {
  const { d, label: mid } = studioBezier({ x: sourceX, y: sourceY, side: SIDE[sourcePosition] }, { x: targetX, y: targetY, side: SIDE[targetPosition] });
  const [hot, setHot] = useState(false);
  const leave = useRef<number>(0);
  useEffect(() => () => window.clearTimeout(leave.current), []);
  const hover = (inside: boolean) => { window.clearTimeout(leave.current); if (inside) setHot(true); else leave.current = window.setTimeout(() => setHot(false), 160); };
  const onRemove = data?.onRemove;
  return <g className="map-link" style={{ ["--studio-link" as string]: data?.tone }} onMouseEnter={() => hover(true)} onMouseLeave={() => hover(false)}>
    <BaseEdge id={id} path={d} style={style} markerEnd={markerEnd} interactionWidth={18} className="map-link__line"
      label={label} labelX={mid.x} labelY={mid.y} labelStyle={{ fill: "var(--studio-text)", fontSize: 10, fontWeight: 600 }}
      labelBgStyle={{ fill: "var(--studio-bg)" }} labelBgPadding={[4, 2]} labelBgBorderRadius={4}/>
    <StudioLinkMotion d={d} mid={mid} motion={data?.motion}/>
    {onRemove ? <LinkTrash at={{ x: sourceX + OUT[sourcePosition].x * TRASH_GAP, y: sourceY + OUT[sourcePosition].y * TRASH_GAP }} shown={hot} onHover={hover} onRemove={() => onRemove(id)}/> : null}
  </g>;
}
