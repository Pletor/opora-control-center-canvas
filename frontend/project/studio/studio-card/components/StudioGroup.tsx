import type { Node, NodeProps } from "@xyflow/react";
import "../styles/studio-card.css";

export type StudioGroupNode = Node<{ label: string }, "studio-group">;

/** Rám skupiny na plátně (komponenty stránky bez sekce): popisek velkými písmeny vlevo nahoře, karty uvnitř. Jen kresba. */
export default function StudioGroup({ data }: NodeProps<StudioGroupNode>) {
  return <div className="studio-group" data-testid="studio-group"><span className="studio-group__label">{data.label}</span></div>;
}
