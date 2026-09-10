import { useEffect, useRef, useState } from "react";
import { api } from "./types";
import { SOURCE_DRAG_TYPE } from "./workspace-selection";

type Entry = { name: string; path: string; kind: "directory" | "file" | "link"; blocked: boolean };
type TreePage = { root: string | null; entries: Entry[]; total: number; hasMore: boolean; nextOffset: number | null; available: boolean; observedAt: string | null };

export default function SourceExplorer({ project, workspace, selected, onSelect, search, refresh, basePath = "", rootLabel = "Podstata a architektura", directoriesOnly = false, rootOnly = false }: {
  project: string; workspace: string; selected: string; onSelect: (path: string, kind: "directory" | "file" | "root") => void; search: string; refresh: number;
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
  const generation = useRef(0);
  async function load(path: string, offset = 0) {
    const ticket = generation.current;
    setPending((old) => new Set(old).add(path)); setError("");
    try {
      const page = await api<TreePage>("/api/workspace/tree?" + new URLSearchParams({ project, workspace, path, offset: String(offset) }));
      if (ticket !== generation.current) return;
      setPages((old) => ({ ...old, [path]: { ...page, entries: offset ? [...new Map([...(old[path]?.entries ?? []), ...page.entries].map((entry) => [entry.path, entry])).values()] : page.entries } }));
    } catch (e) { if (ticket === generation.current) setError(String(e)); }
    finally { if (ticket === generation.current) setPending((old) => { const next = new Set(old); next.delete(path); return next; }); }
  }
  useEffect(() => {
    generation.current++; setPages({}); setExpanded(new Set()); setPending(new Set()); load(basePath);
    return () => { generation.current++; };
  }, [project, workspace, refresh, basePath]);
  function toggle(entry: Entry) {
    const opening = !expanded.has(entry.path);
    setExpanded((old) => { const next = new Set(old); if (opening) next.add(entry.path); else next.delete(entry.path); return next; });
    if (opening && !Object.hasOwn(pages, entry.path) && !pending.has(entry.path)) load(entry.path);
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
        <button type="button" className="source-name" disabled={entry.blocked} title={entry.blocked ? "Odkaz nelze otevřít" : entry.path} onClick={() => onSelect(entry.path, entry.kind === "directory" ? "directory" : "file")}>{entry.name}</button>
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
    {rootLabel && <button type="button" className="project-overview-link" aria-pressed={selected === basePath} onClick={() => onSelect(basePath, "root")}>{rootLabel}</button>}
    <div className="source-tree" role="tree" aria-label="Soubory pracovního prostoru">{rows(basePath, 0)}</div>
    {pages[basePath]?.available === false && <p className="tree-note">Projekt zatím nemá zdrojovou složku. Dokumentaci i Editor lze používat samostatně.</p>}
    {error && <p className="error" role="alert">{error}<button type="button" onClick={() => load(basePath)}>Zkusit znovu</button></p>}
    <footer className="tree-note">Složky se načítají až při rozbalení. Hledání filtruje načtené položky. Interní .git se nezobrazuje.</footer>
  </aside>;
}
