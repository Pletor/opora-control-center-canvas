import type { StructureGroup } from "../logic/structure-model";
import StructureIcon from "./StructureIcon";
import StructureSector from "./StructureSector";
import StructureTile from "./StructureTile";

type Props = {
  group: StructureGroup;
  rootId: string;
  selectedId: string | null;
  disabled: boolean;
  onSelect: (id: string) => void;
  onOpen: (id: string) => void;
  onAddNode: (parentId: string) => void;
  onAddSector: (parentId: string) => void;
};

const sectorCount = (count: number) => (count === 1 ? "1 sektor" : count >= 2 && count <= 4 ? `${count} sektory` : `${count} sektorů`);

/**
 * Oblast (přerušovaný jantarový rám) nebo implicitní skupina přímých dětí rootu bez rámu.
 * „+ Sektor“ v oblasti hlásí id oblasti: sektor patří do oblasti geometricky, rodičem je root.
 */
export default function StructureArea({ group, rootId, selectedId, disabled, onSelect, onOpen, onAddNode, onAddSector }: Props) {
  const framed = group.id !== null;
  const name = group.name.trim() || "Nepojmenovaná oblast";
  return (
    <section
      className={`component-structure__area${framed ? "" : " component-structure__area--loose"}`}
      aria-label={framed ? `Oblast ${name}` : "Prvky mimo oblast"}
    >
      <header className="component-structure__area-head">
        {framed ? (
          <button
            type="button"
            className={`component-structure__area-name${selectedId === group.id ? " component-structure__area-name--selected" : ""}`}
            onClick={() => onSelect(group.id!)}
          >
            <StructureIcon name="area" />
            OBLAST: {name}
          </button>
        ) : (
          <span className="component-structure__area-name">Mimo oblast</span>
        )}
        <span className="component-structure__count">{sectorCount(group.sectors.length)}</span>
        <button type="button" className="component-structure__mini" disabled={disabled} onClick={() => onAddSector(group.id ?? rootId)}>
          + Sektor
        </button>
        {framed ? null : (
          <button type="button" className="component-structure__mini" disabled={disabled} onClick={() => onAddNode(rootId)}>
            + Přidat uzel
          </button>
        )}
      </header>
      {framed && group.purpose.trim() ? <p className="component-structure__area-purpose">{group.purpose}</p> : null}
      <div className="component-structure__sectors">
        {group.sectors.map((sector) => (
          <StructureSector
            key={sector.id}
            sector={sector}
            selectedId={selectedId}
            disabled={disabled}
            onSelect={onSelect}
            onOpen={onOpen}
            onAddNode={onAddNode}
          />
        ))}
      </div>
      {group.items.length ? (
        <div className="component-structure__loose">
          {group.items.map((item) => (
            <StructureTile key={item.id} item={item} selected={item.id === selectedId} onSelect={onSelect} onOpen={onOpen} />
          ))}
        </div>
      ) : null}
    </section>
  );
}
