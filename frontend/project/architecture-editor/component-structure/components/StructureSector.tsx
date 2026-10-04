import type { StructureSector as Sector } from "../logic/structure-model";
import StructureIcon from "./StructureIcon";
import StructureTile from "./StructureTile";

type Props = {
  sector: Sector;
  selectedId: string | null;
  disabled: boolean;
  onSelect: (id: string) => void;
  onOpen: (id: string) => void;
  onAddNode: (parentId: string) => void;
};

const nodeCount = (count: number) => (count === 1 ? "1 uzel" : count >= 2 && count <= 4 ? `${count} uzly` : `${count} uzlů`);

/** Sektor v barvě své vrstvy: hlavička se jménem a počtem uzlů, dlaždice uzlů a přidání uzlu. */
export default function StructureSector({ sector, selectedId, disabled, onSelect, onOpen, onAddNode }: Props) {
  const name = sector.name.trim() || "Bez názvu";
  return (
    <section className={`component-structure__sector component-structure__sector--${sector.tone}`} aria-label={`Sektor ${name}`}>
      <header className="component-structure__sector-head">
        <button
          type="button"
          className={`component-structure__sector-name${selectedId === sector.id ? " component-structure__sector-name--selected" : ""}`}
          onClick={() => onSelect(sector.id)}
          onDoubleClick={() => onOpen(sector.id)}
        >
          <StructureIcon name="sector" />
          SEKTOR: {name}
        </button>
        <span className="component-structure__count">{nodeCount(sector.items.length)}</span>
      </header>
      {sector.items.map((item) => (
        <StructureTile key={item.id} item={item} selected={item.id === selectedId} onSelect={onSelect} onOpen={onOpen} />
      ))}
      <button type="button" className="component-structure__add" disabled={disabled} onClick={() => onAddNode(sector.id)}>
        + Přidat uzel
      </button>
    </section>
  );
}
