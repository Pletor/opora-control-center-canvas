import { useState } from "react";
import type { LibraryOwner } from "@/project/library-canvas/logic/library-api";
import { brainOf, BRAIN_SHELF, shelfCount, shelfId, type ShelfData, type ShelfEntry } from "../logic/component-shelf";
import { flowCount, folderTags } from "../logic/library-shelf";
import { useLibraryShelf } from "../logic/use-library-shelf";
import ShelfCard from "./ShelfCard";
import ShelfForm from "./ShelfForm";
import LibraryFolderView from "./LibraryFolderView";
import BrainArtifactList from "./BrainArtifactList";
import HarnessReadsOverview from "./HarnessReadsOverview";
import "../styles/component-shelf.css";

const OWNER: Record<LibraryOwner, string> = { human: "Člověk", agent: "Agent" };
type Open = { kind: "folder"; id: string } | { kind: "brain"; entry: ShelfEntry } | null;

/** Panel Komponenty vpravo od domén: knihovna pláten toku napříč projekty s přepínačem části Člověk / Agent. Karty jsou
 *  složky (počet pláten, štítky) a za nimi Skills, Tools a Harness, které vedou do čtecího pohledu Brainu jako dřív.
 *  „+ Složka“ (jen část Člověk) a „+ Nové plátno“ ve složce zakládají; plátno se otevírá callbackem `onOpenFlow` (App). */
export default function ComponentShelf({ data, onOpenFlow }: { data: ShelfData; onOpenFlow?: (id: string) => void }) {
  const [owner, setOwner] = useState<LibraryOwner>("human");
  const [open, setOpen] = useState<Open>(null);
  const [adding, setAdding] = useState(false);
  const library = useLibraryShelf(owner);
  const folders = library.folders.data ?? [];
  const folder = open?.kind === "folder" ? folders.find((item) => item.id === open.id) : undefined;
  const brain = open?.kind === "brain" ? open.entry : null;
  const title = folder?.title ?? brain?.label;
  return <aside className="component-shelf" aria-label="Komponenty" data-testid="component-shelf">
    <header className="component-shelf__head">
      <div>
        <h3 className="component-shelf__title">Komponenty</h3>
        <p className="component-shelf__lead">Plátna toků napříč projekty: jak metoda funguje krok za krokem</p>
      </div>
      <div className="component-shelf__owner" role="group" aria-label="Část knihovny">
        {(["human", "agent"] as const).map((part) => <button key={part} type="button" className="component-shelf__owner-option" aria-pressed={owner === part}
          data-testid={"component-shelf-owner-" + part} onClick={() => { setOwner(part); setOpen(null); }}>{OWNER[part]}</button>)}
      </div>
      {owner === "human" && !open && <button type="button" className="component-shelf__create" data-testid="component-shelf-create" onClick={() => setAdding(true)}>+ Složka</button>}
    </header>
    {library.error && <p className="component-shelf__note component-shelf__note--error" role="alert">{library.error}</p>}
    {adding && !open && <ShelfForm testId="library-new-folder-form" title="Název složky" extra="Štítky (např. rag, vektory)" submit="Založit složku" busy={library.busy}
      onSubmit={(name, tags) => { void library.addFolder(name, tags).then(() => setAdding(false)); }} onCancel={() => setAdding(false)}/>}
    {open && title ? <section className="component-shelf__viewer" aria-label={"Knihovna " + title}>
      <div className="component-shelf__viewer-head">
        <button type="button" className="component-shelf__back" data-testid="component-shelf-back" onClick={() => setOpen(null)}>← Komponenty</button>
        <h4 className="component-shelf__viewer-title">{title}</h4>
        <span className="component-shelf__note">{folder ? `${OWNER[owner]} · ${flowCount(folder)}` : "jen ke čtení"}</span>
      </div>
      {folder && <LibraryFolderView folder={folder} busy={library.busy} onOpenFlow={(id) => onOpenFlow?.(id)}
        onAddFlow={(name, description) => { void library.addFlow(folder.id, name, description).then((id) => { if (id) onOpenFlow?.(id); }); }}/>}
      {brain?.source.kind === "brain" && <BrainArtifactList artifacts={brainOf(data.brain.data ?? [], brain.source.artifact)} source={data.brain}/>}
      {brain?.source.kind === "harness" && <HarnessReadsOverview source={data.harness}/>}
    </section> : <div className="component-shelf__grid">
      {library.folders.error && <p className="component-shelf__note" role="alert">Knihovnu se nepodařilo načíst: {library.folders.error}</p>}
      {!library.folders.data && !library.folders.error && <p className="component-shelf__note">Načítám knihovnu…</p>}
      {library.folders.data && !folders.length && <p className="component-shelf__note">Knihovna agenta zatím nemá žádnou složku. Srdce si ji založí samo.</p>}
      {folders.map((item) => <ShelfCard key={item.id} id={`opora:library:${owner}:${item.slug}`} testId={"folder-" + item.slug} badge="Složka" name={item.title}
        count={flowCount(item)} tags={folderTags(item.description)} onOpen={() => setOpen({ kind: "folder", id: item.id })}/>)}
      {BRAIN_SHELF.map((entry) => <ShelfCard key={entry.id} id={shelfId(entry)} testId={entry.id} badge="Knihovna" name={entry.label} count={shelfCount(entry, data)}
        onOpen={() => setOpen({ kind: "brain", entry })}/>)}
    </div>}
  </aside>;
}
