import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "./types";
import { SOURCE_DRAG_TYPE } from "./workspace-selection";

type Entry = { name: string; path: string; kind: "directory" | "file" | "link"; blocked: boolean };
type TreePage = { root: string | null; entries: Entry[]; total: number; hasMore: boolean; nextOffset: number | null; available: boolean; observedAt: string | null; hiddenCount?: number };

const KNOWN_FOLDERS = ["src", "backend", "tests"];

export default function SourceExplorer({ project, workspace, selected, onSelect, search, refresh, basePath = "", rootLabel = "Podstata a architektura", directoriesOnly = false, rootOnly = false, expandKnown = 0, collapseAll = 0, compact = false, visibility, filterPath }: {
  project: string; workspace: string; selected: string; onSelect: (path: string, kind: "directory" | "file" | "root") => void; search: string; refresh: number;
  /** Zúží strom na podadresář (např. adresář sektoru); cesty jsou stále vůči kořeni projektu. */
  basePath?: string;
  rootLabel?: string;
  /** Skryje soubory; použito při výběru adresáře jako budoucího zdroje sektoru. */
  directoriesOnly?: boolean;
  /** Nabídne jen složky přímo v zadaném kořeni, bez vnořeného výběru. */
  rootOnly?: boolean;
  /** Počítadlo požadavků z nástrojů Projektu: rozbalí jen skutečně načtené přímé podsložky src/backend/tests. */
  expandKnown?: number;
  /** Počítadlo požadavků „Sbalit vše“: zavře složky, načtené stránky zůstávají v paměti. */
  collapseAll?: number;
  /** Kompaktní strom používá lištu a filtry rodičovského layoutu místo vlastních panelů. */
  compact?: boolean;
  visibility?: "all" | "working";
  filterPath?: (path: string) => boolean;
}) {
  const [pages, setPages] = useState<Record<string, TreePage>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [showAll, setShowAll] = useState(false);
  const includeAll = visibility ? visibility === "all" : showAll;
  const [actionFile, setActionFile] = useState<Entry | null>(null);
  const [opening, setOpening] = useState(false);
  const [openNotice, setOpenNotice] = useState("");
  const actionMenu = useRef<HTMLDivElement>(null);
  const actionTrigger = useRef<HTMLButtonElement | null>(null);
  const [menuPosition, setMenuPosition] = useState({ left: 0, top: 0 });
  const openLock = useRef(false);
  const generation = useRef(0);
  async function load(path: string, offset = 0) {
    const ticket = generation.current;
    setPending((old) => new Set(old).add(path)); setError("");
    try {
      const page = await api<TreePage>("/api/workspace/tree?" + new URLSearchParams({ project, workspace, path, offset: String(offset), visibility: includeAll ? "all" : "working" }));
      if (ticket !== generation.current) return;
      setPages((old) => ({ ...old, [path]: { ...page, entries: offset ? [...new Map([...(old[path]?.entries ?? []), ...page.entries].map((entry) => [entry.path, entry])).values()] : page.entries } }));
    } catch (e) { if (ticket === generation.current) setError(String(e)); }
    finally { if (ticket === generation.current) setPending((old) => { const next = new Set(old); next.delete(path); return next; }); }
  }
  useEffect(() => {
    generation.current++; setPages({}); setExpanded(new Set()); setPending(new Set());
    setActionFile(null); setOpenNotice(""); load(basePath);
    return () => { generation.current++; };
  }, [project, workspace, refresh, basePath, includeAll]);
  useEffect(() => {
    if (!actionFile) return;
    actionMenu.current?.querySelector<HTMLButtonElement>("button")?.focus({ preventScroll: true });
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !actionMenu.current?.contains(event.target) && !actionTrigger.current?.contains(event.target)) setActionFile(null);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      actionTrigger.current?.focus({ preventScroll: true });
      setActionFile(null);
    };
    const reposition = () => setActionFile(null);
    const scroll = (event: Event) => { if (!(event.target instanceof Node) || !actionMenu.current?.contains(event.target)) reposition(); };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    document.addEventListener("scroll", scroll, true);
    window.addEventListener("resize", reposition);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
      document.removeEventListener("scroll", scroll, true);
      window.removeEventListener("resize", reposition);
    };
  }, [actionFile]);
  useEffect(() => { setActionFile(null); }, [search, collapseAll]);
  async function openFile(entry: Entry, action: "vscode" | "folder" | "folder-vscode") {
    if (openLock.current || entry.blocked || entry.kind === "link") return;
    openLock.current = true; setOpening(true); setError(""); setOpenNotice("");
    const ticket = generation.current;
    try {
      const result = await api<{ project: string; workspace: string; path: string; action: string; status: string }>(
        "/api/workspace/open-file", { project, workspace, path: entry.path, action });
      if (ticket !== generation.current) return;
      if (result.project !== project || result.workspace !== workspace || result.path !== entry.path || result.action !== action || result.status !== "requested") {
        throw new Error("Odpověď neodpovídá vybranému souboru.");
      }
      setOpenNotice(`Požadavek na otevření ${action === "folder" ? "složky umístění" : action === "folder-vscode" ? "složky ve VS Code" : "ve VS Code"} předán systému: ${entry.path}`);
      actionTrigger.current?.focus({ preventScroll: true });
      setActionFile(null);
    } catch (e) { if (ticket === generation.current) setError(String(e)); }
    finally { openLock.current = false; setOpening(false); }
  }
  useEffect(() => {
    // Žádné rekurzivní procházení disku ani vymyšlené složky: jen položky už vrácené serverem pro kořen.
    if (!expandKnown || rootOnly) return;
    const known = (pages[basePath]?.entries ?? []).filter((entry) => entry.kind === "directory" && !entry.blocked && KNOWN_FOLDERS.includes(entry.name));
    if (!known.length) return;
    setExpanded((old) => new Set([...old, ...known.map((entry) => entry.path)]));
    for (const entry of known) if (!Object.hasOwn(pages, entry.path) && !pending.has(entry.path)) load(entry.path);
  }, [expandKnown]);
  // Pozdní odpověď load() mění jen pages/pending, nikdy expanded, takže sbalenou složku znovu neotevře.
  useEffect(() => { if (collapseAll) setExpanded(new Set()); }, [collapseAll]);
  function toggle(entry: Entry) {
    const opening = !expanded.has(entry.path);
    setExpanded((old) => { const next = new Set(old); if (opening) next.add(entry.path); else next.delete(entry.path); return next; });
    if (opening && !Object.hasOwn(pages, entry.path) && !pending.has(entry.path)) load(entry.path);
  }
  const needle = search.toLocaleLowerCase();
  function rows(path: string, depth: number): React.ReactNode {
    const page = Object.hasOwn(pages, path) ? pages[path] : undefined;
    return <>{page?.entries.filter((entry) => !filterPath || filterPath(entry.path)).filter((entry) => directoriesOnly ? entry.kind === "directory" : true).filter((entry) => !needle || entry.kind === "directory" || entry.path.toLocaleLowerCase().includes(needle)).map((entry) => <div key={entry.path}>
      <div role="treeitem" aria-selected={selected === entry.path} aria-expanded={entry.kind === "directory" && !rootOnly ? expanded.has(entry.path) : undefined}
        className={"source-row" + (selected === entry.path ? " selected" : "")} style={{ paddingLeft: 8 + depth * 14 }}
        draggable={!entry.blocked} onDragStart={(e) => {
          e.dataTransfer.setData(SOURCE_DRAG_TYPE, JSON.stringify({ project, workspace, path: entry.path })); e.dataTransfer.effectAllowed = "copy";
        }}>
        {entry.kind === "directory" && !rootOnly ? <button type="button" className="source-toggle" aria-label={(expanded.has(entry.path) ? "Sbalit " : "Rozbalit ") + entry.name}
          onClick={() => { setActionFile(null); toggle(entry); }}>{expanded.has(entry.path) ? "⌄" : "›"}</button> : <span className="source-file-mark" aria-hidden="true">{entry.blocked ? "↗" : "·"}</span>}
        <button type="button" className="source-name" disabled={entry.blocked} title={entry.blocked ? "Odkaz nelze otevřít" : entry.path}
          aria-haspopup="menu" aria-expanded={actionFile?.path === entry.path}
          onClick={(event) => {
            onSelect(entry.path, entry.kind === "directory" ? "directory" : "file");
            setOpenNotice("");
            actionTrigger.current = event.currentTarget;
            const rect = event.currentTarget.getBoundingClientRect();
            setMenuPosition({ left: Math.max(8, Math.min(rect.left, window.innerWidth - 276)), top: Math.max(8, Math.min(rect.bottom + 4, window.innerHeight - 158)) });
            setActionFile(actionFile?.path !== entry.path ? entry : null);
          }}>{entry.name}</button>
      </div>

      {!rootOnly && expanded.has(entry.path) && <div role="group">{rows(entry.path, depth + 1)}</div>}
    </div>)}
    {pending.has(path) && <p role="status" className="tree-note">Načítám složku…</p>}
    {page?.hasMore && <button type="button" className="tree-more" disabled={pending.has(path)} onClick={() => load(path, page.nextOffset!)}>Načíst další ({page.entries.length}/{page.total})</button>}
    </>;
  }
  return <aside className="source-explorer" aria-label="Zdrojový strom">
    {!compact && <><div className="source-heading"><div className="eyebrow">WORKSPACE / SOUBORY 1:1</div><h2>Strom projektu</h2>
      <code>{pages[basePath]?.root || "Bez připojeného adresáře"}</code></div>
    <label className="tree-visibility"><input type="checkbox" checked={showAll}
      onChange={(e) => { generation.current++; setShowAll(e.target.checked); }} />
      Zobrazit i ignorované a technické soubory</label></>}
    {rootLabel && <button type="button" className="project-overview-link" aria-pressed={selected === basePath} onClick={() => onSelect(basePath, "root")}>{rootLabel}</button>}
    <div className="source-tree" role="tree" aria-label="Soubory pracovního prostoru">{rows(basePath, 0)}</div>
    {pages[basePath]?.available === false && <p className="tree-note">Projekt zatím nemá zdrojovou složku. Dokumentaci i Editor lze používat samostatně.</p>}
    {error && <p className="error" role="alert">{error}<button type="button" onClick={() => load(basePath)}>Zkusit znovu</button></p>}
    {openNotice && <p className="tree-note" role="status">{openNotice}</p>}
    {actionFile && createPortal(<div ref={actionMenu} className="source-file-actions" role="menu" aria-label={`Otevřít ${actionFile.name}`} style={menuPosition}
      onKeyDown={(event) => {
        const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
        const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
        if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
          event.preventDefault();
          const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
          buttons[next]?.focus();
        }
        if (event.key === "Tab") setActionFile(null);
      }}>
      <button type="button" role="menuitem" disabled={opening} onClick={() => void openFile(actionFile, "vscode")}>Otevřít ve VS Code</button>
      <button type="button" role="menuitem" disabled={opening} title={actionFile.kind === "directory" ? "Otevře vybranou složku v Průzkumníku" : "Otevře složku obsahující soubor v Průzkumníku"} onClick={() => void openFile(actionFile, "folder")}>Otevřít složku umístění</button>
      <button type="button" role="menuitem" disabled={opening} onClick={() => void openFile(actionFile, "folder-vscode")}>Otevřít složku ve VS Code</button>
    </div>, document.body)}
    {!compact && <footer className="tree-note">{showAll ? "Úplný přehled mimo interní .git." : "Pracovní přehled: .gitignore, závislosti a cache jsou skryté, src je první."}
      {!showAll && !!pages[basePath]?.hiddenCount && ` Skryto v této složce: ${pages[basePath].hiddenCount}.`}
      {" "}Nic se nemaže z disku. Složky se načítají až při rozbalení; hledání prochází načtené položky.</footer>}
  </aside>;
}
