import { PALETTE_DRAG_TYPE } from "@/shared/flow-editor/node-palette/logic/palette";
import type { PaletteGroup as Group } from "../logic/palette-groups";

/** Jedna skupina katalogu: hlavička s názvem a počtem sbalí nebo rozbalí seznam; položka nese ikonu typu, název,
 * poskytovatele a souhrn portů. Položku jde přetáhnout na plátno (nese id typu) nebo kliknutím přidat. */
export default function PaletteGroup({ group, open, onToggle, onAdd }: { group: Group; open: boolean; onToggle: () => void; onAdd: (typeId: string) => void }) {
  return <section className="studio-model-palette__group" data-testid={"studio-model-palette-group-" + group.id}>
    <button type="button" className="studio-model-palette__group-head" aria-expanded={open} onClick={onToggle}>
      <span className="studio-model-palette__chevron" aria-hidden="true">{open ? "▾" : "▸"}</span>
      {group.id}<small className="studio-model-palette__count">{group.items.length}</small>
    </button>
    {open && <ul className="studio-model-palette__list">
      {group.items.map((item) => <li key={item.id}>
        <button type="button" className="studio-model-palette__item" draggable data-testid={"studio-model-add-" + item.id}
          title={`Přidat ${item.name} (klik), nebo přetáhnout na plátno`} onClick={() => onAdd(item.id)}
          onDragStart={(event) => { event.dataTransfer.setData(PALETTE_DRAG_TYPE, item.id); event.dataTransfer.effectAllowed = "copy"; }}>
          <span className="studio-model-palette__icon" aria-hidden="true">{item.icon}</span>
          <span className="studio-model-palette__text">
            <strong className="studio-model-palette__name">{item.name}{item.provider && <small className="studio-model-palette__provider">{item.provider}</small>}</strong>
            <small className="studio-model-palette__summary">{item.summary}</small>
          </span>
          <span className="studio-model-palette__plus" aria-hidden="true">⊕</span>
        </button>
      </li>)}
    </ul>}
  </section>;
}
