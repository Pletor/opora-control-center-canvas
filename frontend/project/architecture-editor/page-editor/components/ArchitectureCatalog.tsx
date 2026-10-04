import { useState } from "react";
import { CATALOG_DRAG_TYPE, CATALOG_ITEMS } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { CATEGORY_ICON, libraryFamilies } from "../logic/library-families";
import PageIcon from "./PageIcon";

/** Library families as colored groups of tiles; drag onto the map or click a tile to insert. */
export default function ArchitectureCatalog({ disabled, scopeName, onInsert }: { disabled: boolean; scopeName: string; onInsert: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const groups = libraryFamilies(CATALOG_ITEMS, query);
  const toggle = (id: string) => setClosed((set) => { const next = new Set(set); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  return <div className="page-library">
    <input className="page-library__search" type="search" aria-label="Hledat prvek architektury" placeholder="Hledat prvek…"
      value={query} onChange={(event) => setQuery(event.target.value)}/>
    <p className="page-library__hint">Vložit do: <strong className="page-library__scope">{scopeName}</strong>. Přetažením na kartu vložíte potomka.</p>
    {groups.map(({ family, items }) => {
      const expanded = !closed.has(family.id);
      return <section key={family.id} className={`page-library__family page-library__family--${family.tone}`} data-testid={"architecture-family-" + family.id}>
        <button type="button" className="page-library__family-head" aria-expanded={expanded} onClick={() => toggle(family.id)}>
          <span className="page-library__family-label">{family.label}</span>
          <span className="page-library__count">{items.length}</span>
          <span className="page-library__caret" aria-hidden="true">{expanded ? "▴" : "▾"}</span>
        </button>
        {expanded && <div className="page-library__tiles">{items.map((item) => <button key={item.id} type="button" className="page-library__tile"
          title={item.purpose} draggable={!disabled} disabled={disabled} data-testid={"architecture-item-" + item.id}
          aria-label={`Vložit ${item.label}`} onClick={() => onInsert(item.id)}
          onDragStart={(event) => { event.dataTransfer.setData(CATALOG_DRAG_TYPE, item.id); event.dataTransfer.effectAllowed = "copy"; }}>
          <PageIcon name={CATEGORY_ICON[item.category]} size={22} className="page-library__tile-icon"/>
          <span className="page-library__tile-label">{item.label}</span>
        </button>)}</div>}
      </section>;
    })}
    {!groups.length && <p className="page-library__hint">Žádný prvek neodpovídá hledání.</p>}
  </div>;
}
