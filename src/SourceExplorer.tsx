import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { api } from "./types";
import { SOURCE_DRAG_TYPE, allowedReference } from "./workspace-selection";

type Entry = { name: string; path: string; kind: "directory" | "file" | "link"; blocked: boolean };
type TreePage = { root: string | null; entries: Entry[]; total: number; hasMore: boolean; nextOffset: number | null; available: boolean; observedAt: string | null; hiddenCount?: number };
/** Ovládání stromu z nadřazené lišty; pracuje jen s již načtenými položkami. */
export type SourceExplorerHandle = { expandKnown: (names: readonly string[]) => number; collapseAll: () => void };

export default function SourceExplorer({ project, workspace, selected, onSelect, search, refresh, basePath = "", rootLabel = "Podstata a architektura", directoriesOnly = false, rootOnly = false, controlRef, onClearSearch, onAddReference }: {
  project: string; workspace: string; selected: string; onSelect: (path: string, kind: "directory" | "file" | "root") => void; search: string; refresh: number;
  /** Volitelné ovládání pro lištu Projektu; ostatní použití stromu se nemění. */
  controlRef?: Ref<SourceExplorerHandle>;
  /** Když je zadán, aktivní hledání ukáže poznámku s tlačítkem Zrušit. */
  onClearSearch?: () => void;
  /** Když je zadán, Ctrl+A na názvu řádku přidá právě tento řádek do kontextu Editoru. */
  onAddReference?: (path: string) => void;
  /** Zúží strom na podadresář (např. adresář sektoru); cesty jsou stále vůči kořeni projektu. */
  basePath?: string;
  rootLabel?: string;
  /** Skryje soubory; použito při výběru adresáře jako budoucího zdroje sektoru. */
  directoriesOnly?: boolean;
  /** Nabídne jen složky přímo v zadaném kořeni, bez vnořeného výběru. */
  rootOnly?: boolean;
}) {
  const [pages, setPages] = useState<Record<string, TreePage>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [showAll, setShowAll] = useState(false);
  const generation = useRef(0);
  async function load(path: string, offset = 0) {
    const ticket = generation.current;
    setPending((old) => new Set(old).add(path)); setError("");
    try {
      const page = await api<TreePage>("/api/workspace/tree?" + new URLSearchParams({ project, workspace, path, offset: String(offset), visibility: showAll ? "all" : "working" }));
      if (ticket !== generation.current) return;
      setPages((old) => ({ ...old, [path]: { ...page, entries: offset ? [...new Map([...(old[path]?.entries ?? []), ...page.entries].map((entry) => [entry.path, entry])).values()] : page.entries } }));
    } catch (e) { if (ticket === generation.current) setError(String(e)); }
    finally { if (ticket === generation.current) setPending((old) => { const next = new Set(old); next.delete(path); return next; }); }
  }
  useEffect(() => {
    generation.current++; setPages({}); setExpanded(new Set()); setPending(new Set()); load(basePath);
    return () => { generation.current++; };
  }, [project, workspace, refresh, basePath, showAll]);
  function toggle(entry: Entry) {
    const opening = !expanded.has(entry.path);
    setExpanded((old) => { const next = new Set(old); if (opening) next.add(entry.path); else next.delete(entry.path); return next; });
    if (opening && !Object.hasOwn(pages, entry.path) && !pending.has(entry.path)) load(entry.path);
  }
  useImperativeHandle(controlRef, () => ({
    expandKnown(names) {
      // Jen přímé, skutečně načtené složky kořene; nic se neprochází rekurzivně ani nevymýšlí.
      if (rootOnly) return 0;
      const targets = (pages[basePath]?.entries ?? []).filter((entry) => entry.kind === "directory" && !entry.blocked && names.includes(entry.name));
      setExpanded((old) => new Set([...old, ...targets.map((entry) => entry.path)]));
      for (const entry of targets) if (!Object.hasOwn(pages, entry.path) && !pending.has(entry.path)) load(entry.path);
      return targets.length;
    },
    // Načtené stránky zůstávají v paměti; běžící načítání rozbalení nemění, takže složku znovu neotevře.
    collapseAll() { setExpanded(new Set()); },
  }));
  // Odkazy, blokované a citlivé či technické cesty do kontextu nepatří.
  const referenceable = (entry: Entry) => !entry.blocked && entry.kind !== "link" && allowedReference(entry.path);
  function rowKey(e: React.KeyboardEvent<HTMLButtonElement>, entry: Entry) {
    if (e.target !== e.currentTarget || e.shiftKey || e.altKey) return;
    const branch = entry.kind === "directory" && !rootOnly;
    if (!e.ctrlKey && !e.metaKey && branch && (e.key === "ArrowRight" ? !expanded.has(entry.path) : e.key === "ArrowLeft" && expanded.has(entry.path))) {
      e.preventDefault(); toggle(entry);
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a" && onAddReference) {
      e.preventDefault(); if (referenceable(entry)) onAddReference(entry.path);
    }
  }
  const needle = search.toLocaleLowerCase();
  function rows(path: string, depth: number): React.ReactNode {
    const page = Object.hasOwn(pages, path) ? pages[path] : undefined;
    return <>{page?.entries.filter((entry) => directoriesOnly ? entry.kind === "directory" : true).filter((entry) => !needle || entry.kind === "directory" || entry.path.toLocaleLowerCase().includes(needle)).map((entry) => <div key={entry.path}>
      <div role="treeitem" aria-selected={selected === entry.path} aria-expanded={entry.kind === "directory" && !rootOnly ? expanded.has(entry.path) : undefined}
        className={"source-row" + (selected === entry.path ? " selected" : "")} style={{ paddingLeft: 8 + depth * 14 }}
        draggable={!entry.blocked} onDragStart={(e) => {
          e.dataTransfer.setData(SOURCE_DRAG_TYPE, JSON.stringify({ project, workspace, path: entry.path })); e.dataTransfer.effectAllowed = "copy";
        }}>
        {entry.kind === "directory" && !rootOnly ? <button type="button" className="source-toggle" aria-label={(expanded.has(entry.path) ? "Sbalit " : "Rozbalit ") + entry.name}
          onClick={() => toggle(entry)}>{expanded.has(entry.path) ? "⌄" : "›"}</button> : <span className="source-file-mark" aria-hidden="true">{entry.blocked ? "↗" : "·"}</span>}
        <button type="button" className="source-name" disabled={entry.blocked} title={entry.blocked ? "Odkaz nelze otevřít" : entry.path} onClick={() => onSelect(entry.path, entry.kind === "directory" ? "directory" : "file")}
          onKeyDown={(e) => rowKey(e, entry)}>{entry.name}</button>
        {onAddReference && <button type="button" className="source-add" disabled={!referenceable(entry)} onClick={() => onAddReference(entry.path)}
          title={referenceable(entry) ? `Přidat ${entry.path} do kontextu Editoru` : "Odkaz, blokovanou, citlivou ani technickou cestu nelze přidat do kontextu."}>+ Editor</button>}
      </div>
      {!rootOnly && expanded.has(entry.path) && <div role="group">{rows(entry.path, depth + 1)}</div>}
    </div>)}
    {pending.has(path) && <p role="status" className="tree-note">Načítám složku…</p>}
    {page?.hasMore && <button type="button" className="tree-more" disabled={pending.has(path)} onClick={() => load(path, page.nextOffset!)}>Načíst další ({page.entries.length}/{page.total})</button>}
    </>;
  }
  return <aside className="source-explorer" aria-label="Zdrojový strom">
    <div className="source-heading"><div className="eyebrow">WORKSPACE / SOUBORY 1:1</div><h2>Strom projektu</h2>
      <code>{pages[basePath]?.root || "Bez připojeného adresáře"}</code></div>
    <label className="tree-visibility"><input type="checkbox" checked={showAll}
      onChange={(e) => { generation.current++; setShowAll(e.target.checked); }} />
      Zobrazit i ignorované a technické soubory</label>
    {onClearSearch && search && <p className="tree-note tree-search-note">Hledání „{search}“ prochází jen načtené složky.
      <button type="button" onClick={onClearSearch}>Zrušit</button></p>}
    {rootLabel && <button type="button" className="project-overview-link" aria-pressed={selected === basePath} onClick={() => onSelect(basePath, "root")}>{rootLabel}</button>}
    <div className="source-tree" role="tree" aria-label="Soubory pracovního prostoru">{rows(basePath, 0)}</div>
    {pages[basePath]?.available === false && <p className="tree-note">Projekt zatím nemá zdrojovou složku. Dokumentaci i Editor lze používat samostatně.</p>}
    {error && <p className="error" role="alert">{error}<button type="button" onClick={() => load(basePath)}>Zkusit znovu</button></p>}
    <footer className="tree-note">{showAll ? "Úplný přehled mimo interní .git." : "Pracovní přehled: .gitignore, závislosti a cache jsou skryté, src je první."}
      {!showAll && !!pages[basePath]?.hiddenCount && ` Skryto v této složce: ${pages[basePath].hiddenCount}.`}
      {" "}Nic se nemaže z disku. Složky se načítají až při rozbalení; hledání prochází načtené položky.</footer>
  </aside>;
}
