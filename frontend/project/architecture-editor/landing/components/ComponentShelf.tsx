import { useState } from "react";
import { brainOf, COMPONENT_SHELF, shelfCount, shelfItems, type ShelfData, type ShelfEntry } from "../logic/component-shelf";
import ShelfCard from "./ShelfCard";
import CatalogFamilyViewer from "./CatalogFamilyViewer";
import BrainArtifactList from "./BrainArtifactList";
import HarnessReadsOverview from "./HarnessReadsOverview";
import "../styles/component-shelf.css";

const CREATE_LATER = "Tvorba vlastní komponenty přijde v dalším milníku";

/** Panel Komponenty right of the domains: a grid of library cards; "Vstup do editoru" swaps the grid for a read-only viewer
 *  of that library (catalog templates, Brain artifacts or the Harness overview). Data come ready from ArchitectureLanding. */
export default function ComponentShelf({ data }: { data: ShelfData }) {
  const [open, setOpen] = useState<ShelfEntry | null>(null);
  const source = open?.source;
  return <aside className="component-shelf" aria-label="Komponenty" data-testid="component-shelf">
    <header className="component-shelf__head">
      <div>
        <h3 className="component-shelf__title">Komponenty</h3>
        <p className="component-shelf__lead">Izolovaná tvorba univerzálních komponent do knihovny</p>
      </div>
      <button type="button" className="component-shelf__create" disabled title={CREATE_LATER} data-testid="component-shelf-create">+ Vytvořit</button>
    </header>
    {open && source ? <section className="component-shelf__viewer" aria-label={"Knihovna " + open.label}>
      <div className="component-shelf__viewer-head">
        <button type="button" className="component-shelf__back" data-testid="component-shelf-back" onClick={() => setOpen(null)}>← Komponenty</button>
        <h4 className="component-shelf__viewer-title">{open.label}</h4>
        <span className="component-shelf__note">jen ke čtení</span>
      </div>
      {source.kind === "catalog" && <CatalogFamilyViewer items={shelfItems(open)}/>}
      {source.kind === "brain" && <BrainArtifactList artifacts={brainOf(data.brain.data ?? [], source.artifact)} source={data.brain}/>}
      {source.kind === "harness" && <HarnessReadsOverview source={data.harness}/>}
    </section> : <div className="component-shelf__grid">
      {COMPONENT_SHELF.map((entry) => <ShelfCard key={entry.id} entry={entry} count={shelfCount(entry, data)} onOpen={() => setOpen(entry)}/>)}
    </div>}
  </aside>;
}
