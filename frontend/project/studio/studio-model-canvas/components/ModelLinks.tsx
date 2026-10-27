import { ViewportPortal } from "@xyflow/react";
import type { ModelLinkView } from "../logic/model-flow";
import type { ConnectDrag } from "../logic/use-connect-drag";

/** Vazby MODELu v souřadnicích plátna (vrstva pod kartami): Bézierova křivka v barvě datového typu, vypnutá vazba
 * čárkovaná a tlumená, vybraná silnější se svitem, popisek uprostřed. Široká neviditelná stopa dovolí vazbu
 * vybrat (`onSelect`). Během tahu nové vazby čárkovaný náhled od portu ke kurzoru. */
export default function ModelLinks({ links, drag, dragColor, onSelect }: { links: ModelLinkView[]; drag: ConnectDrag | null; dragColor: string; onSelect: (id: string) => void }) {
  return <ViewportPortal>
    <svg className="studio-model-canvas__links" width="1" height="1" aria-label="Vazby modelu">
      {links.map((link) => <g key={link.id} className={"studio-model-canvas__link" + (link.inactive ? " studio-model-canvas__link--inactive" : "") + (link.selected ? " studio-model-canvas__link--selected" : "")}
        style={{ ["--studio-link" as string]: link.color }} data-testid={"studio-model-link-" + link.id}>
        <title>{`${link.type}${link.label ? " · " + link.label : ""}${link.inactive ? " · vypnuto" : ""}`}</title>
        <path className="studio-model-canvas__link-hit" d={link.d} onClick={(event) => { event.stopPropagation(); onSelect(link.id); }}/>
        <path className="studio-model-canvas__link-line" d={link.d}/>
        {link.label && <text className="studio-model-canvas__link-label" x={link.mid.x} y={link.mid.y - 6}>{link.label}</text>}
      </g>)}
      {drag && <path className="studio-model-canvas__preview" style={{ ["--studio-link" as string]: dragColor }}
        d={`M ${drag.from.x} ${drag.from.y} C ${(drag.from.x + drag.to.x) / 2} ${drag.from.y} ${(drag.from.x + drag.to.x) / 2} ${drag.to.y} ${drag.to.x} ${drag.to.y}`}/>}
    </svg>
  </ViewportPortal>;
}
