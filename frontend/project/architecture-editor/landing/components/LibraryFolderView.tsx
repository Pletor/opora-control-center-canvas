import { useState } from "react";
import type { LibraryFolder } from "@/project/library-canvas/logic/library-api";
import CopyIdButton from "@/ui-kit/copy-id/components/CopyIdButton";
import { flowFacts, promotionSuggested } from "../logic/library-shelf";
import ShelfForm from "./ShelfForm";

/** Obsah složky knihovny: karty pláten toku (titulek, popis, aktivní verze, počet odvozených; kopie z projektu nese
 *  „vychází z …“ až na plátně; ověřené plátno agenta nese „navrženo k povýšení“) a „+ Nové plátno“, které plátno založí a otevře. Klik na kartu otevře plátno. */
export default function LibraryFolderView({ folder, busy, onOpenFlow, onAddFlow }: {
  folder: LibraryFolder; busy: boolean; onOpenFlow: (id: string) => void; onAddFlow: (title: string, description: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  return <div className="component-shelf__folder" data-testid={"library-folder-" + folder.slug}>
    {folder.description && <p className="component-shelf__note">{folder.description}</p>}
    <div className="component-shelf__flows">
      {folder.flows.map((flow) => <article key={flow.id} className="component-shelf__flow" data-testid={"library-flow-" + (flow.slug ?? flow.id)}>
        <div className="component-shelf__card-top">
          <button type="button" className="component-shelf__flow-title" onClick={() => onOpenFlow(flow.id)}>{flow.title} ↗</button>
          <CopyIdButton id={flow.ownerRef} label="ID plátna"/>
        </div>
        {flow.description && <p className="component-shelf__purpose">{flow.description}</p>}
        <p className="component-shelf__count component-shelf__count--left">{flowFacts(flow)}</p>
        {promotionSuggested(flow) && <p className="component-shelf__suggest" data-testid={"library-suggest-" + (flow.slug ?? flow.id)}>ověřeno v projektu – navrženo k povýšení</p>}
      </article>)}
      {!folder.flows.length && <p className="component-shelf__note">Ve složce zatím není žádné plátno toku.</p>}
    </div>
    {adding ? <ShelfForm testId="library-new-flow-form" title="Titulek plátna (např. RAG – ingest a dotaz)" extra="Popis: co metoda dělá" submit="Založit a otevřít" busy={busy}
      onSubmit={(title, description) => { onAddFlow(title, description); setAdding(false); }} onCancel={() => setAdding(false)}/>
      : <button type="button" className="component-shelf__add" data-testid="library-new-flow" onClick={() => setAdding(true)}>+ Nové plátno</button>}
  </div>;
}
