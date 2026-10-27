import { useMemo, useState } from "react";
import { paletteGroups } from "../logic/palette-groups";
import PaletteGroup from "./PaletteGroup";
import "../styles/studio-model-palette.css";

/** Katalog komponent vlevo od plátna MODELu: hledání nahoře, pod ním sbalitelné skupiny typů. Klik na položku nebo
 * tlačítko ⊕ přidá komponentu na volné místo, přetažení ji položí tam, kam ji člověk pustí. Přidání hlásí rodiči. */
export default function ModelPalette({ onAdd }: { onAdd: (typeId: string) => void }) {
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const groups = useMemo(() => paletteGroups(query), [query]);
  const total = groups.reduce((sum, group) => sum + group.items.length, 0);
  const toggle = (id: string) => setCollapsed((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  return <aside className="studio-model-palette" aria-label="Katalog komponent" data-testid="studio-model-palette">
    <header className="studio-model-palette__title"><span>Katalog komponent</span><small className="studio-model-palette__count">{total}</small></header>
    <div className="studio-model-palette__search">
      <input className="studio-model-palette__input" type="search" value={query} placeholder="Hledat komponentu, port, poskytovatele…"
        aria-label="Hledat v katalogu" data-testid="studio-model-palette-search" onChange={(event) => setQuery(event.target.value)}/>
      {query && <button type="button" className="studio-model-palette__clear" onClick={() => setQuery("")} aria-label="Vymazat hledání">×</button>}
    </div>
    {groups.map((group) => <PaletteGroup key={group.id} group={group} open={!collapsed.has(group.id) || !!query} onToggle={() => toggle(group.id)} onAdd={onAdd}/>)}
    {!groups.length && <p className="studio-model-palette__empty">Nic neodpovídá hledání.</p>}
  </aside>;
}
