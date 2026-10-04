import { STATUS_LABEL, type StructureItem } from "../logic/structure-model";
import StructureIcon from "./StructureIcon";

type Props = {
  item: StructureItem;
  selected: boolean;
  onSelect: (id: string) => void;
  onOpen: (id: string) => void;
};

/** Dlaždice uzlu: klik vybere, dvojklik otevře jeho vnitřní strukturu. */
export default function StructureTile({ item, selected, onSelect, onOpen }: Props) {
  const name = item.name.trim() || "Bez názvu";
  return (
    <button
      type="button"
      className={`component-structure__tile component-structure__tile--${item.tone}${selected ? " component-structure__tile--selected" : ""}`}
      aria-pressed={selected}
      title="Klik vybere, dvojklik otevře vnitřní strukturu"
      onClick={() => onSelect(item.id)}
      onDoubleClick={() => onOpen(item.id)}
    >
      <span className="component-structure__tile-icon">
        <StructureIcon name={item.kind === "sector" ? "sector" : item.tone} />
      </span>
      <span className="component-structure__tile-text">
        <span className="component-structure__tile-name">{name}</span>
        <span className="component-structure__tile-purpose">{item.purpose.trim() || "Účel zatím nic"}</span>
      </span>
      <span className={`component-structure__status component-structure__status--${item.status}`}>{STATUS_LABEL[item.status]}</span>
    </button>
  );
}
