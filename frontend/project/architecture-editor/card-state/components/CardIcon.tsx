import type { CanvasNode } from "@/shared/types/logic/types";
import StudioCardIcon from "@/project/studio/studio-card/components/StudioCardIcon";
import { cardIcon } from "../logic/card-state";
import "../styles/card-state.css";

/** Ikona druhu karty (Lucide jako ve Studiu) v rámečku 18 px; barvu dědí z `color` rodiče. Jen kresba. */
export default function CardIcon({ node, className = "" }: { node: CanvasNode; className?: string }) {
  return <span className={("card-state__icon " + className).trim()} aria-hidden="true"><StudioCardIcon name={cardIcon(node)}/></span>;
}
