import { NodeResizer, Position } from "@xyflow/react";
import { AREA_SIZE_MAX, AREA_SIZE_MIN } from "@/editor/canvas/area/logic/area-model";
import PortHandle from "@/shared/flow-ports/components/PortHandle";
import PageIcon from "../../components/PageIcon";
import type { CardData } from "./ArchitectureCard";

/** Oblast jako skupina Studia: průsvitný čárkovaný rám s popiskem velkými písmeny vlevo nahoře, počtem sektorů a
 * „+ Sektor“; vybraná ukáže tahadla rozměru (ustálený rozměr hlásí `actions.resizeArea`). Porty `flow` na bocích. */
export default function AreaFrame({ data, selected }: { data: CardData; selected: boolean }) {
  const { node, actions } = data;
  return <article className={"map-card map-card--area" + (selected ? " map-card--selected" : "")} data-testid={"architecture-card-" + node.id}>
    <NodeResizer isVisible={selected && !data.disabled} minWidth={AREA_SIZE_MIN} minHeight={AREA_SIZE_MIN} maxWidth={AREA_SIZE_MAX} maxHeight={AREA_SIZE_MAX}
      lineClassName="map-card__resize-line" handleClassName="map-card__resize-handle"
      onResizeEnd={(_, params) => actions.resizeArea(node.id, params.width, params.height)}/>
    <PortHandle kind="flow" type="target" position={Position.Left} className={"map-card__port map-card__port--" + (data.ports.in ?? "open")}/>
    <PortHandle kind="flow" type="source" position={Position.Right} className={"map-card__port map-card__port--" + (data.ports.out ?? "open")}/>
    <header className="map-card__area-head">
      <PageIcon name="area" size={14} className="map-card__area-icon"/>
      <strong className="map-card__area-title">OBLAST: {node.name}</strong>
      <span className="map-card__area-count">{data.areaLabel}</span>
      <button type="button" className="map-card__area-add nodrag" disabled={data.disabled} data-testid={"architecture-area-sector-" + node.id}
        aria-label={`Přidat sektor do oblasti ${node.name}`} onClick={() => actions.addSector(node.id)}>+ Sektor</button>
    </header>
    {node.purpose && <p className="map-card__area-purpose">{node.purpose}</p>}
  </article>;
}
