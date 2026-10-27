import type { CanvasNode } from "@/shared/types/logic/types";
import { toneOf } from "../../logic/canvas-model";
import CardIcon from "../../../card-state/components/CardIcon";
import type { CardActions } from "./ArchitectureCard";

/** Řádek „stupňů“ jako karta MODELu Studia: až tři přímí potomci jako stejně široké buňky (ikona vrstvy a název, účel
 * v bublině), za nimi „+ N dalších“. Klik potomka vybere, dvojklik otevře jeho detail. */
export default function CardStages({ preview, more, actions }: { preview: CanvasNode[]; more: number; actions: CardActions }) {
  if (!preview.length) return null;
  return <ul className="map-card__stages">
    {preview.map((child) => <li key={child.id} className="map-card__stage-item">
      <button type="button" className={`map-card__stage map-card__stage--${toneOf(child)} nodrag`} data-testid={"architecture-child-" + child.id}
        title={child.purpose ? `${child.name} – ${child.purpose}` : child.name}
        onClick={(event) => { event.stopPropagation(); actions.select(child.id); }}
        onDoubleClick={(event) => { event.stopPropagation(); actions.openStructure(child.id); }}>
        <CardIcon node={child} className="map-card__stage-icon"/>
        <span className="map-card__stage-name">{child.name}</span>
      </button>
    </li>)}
    {more > 0 && <li className="map-card__more">+ {more} dalších</li>}
  </ul>;
}
