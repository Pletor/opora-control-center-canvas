import AgentContextPanel from "@/project/architecture-editor/element-detail/components/AgentContextPanel";
import BriefStatus from "@/project/architecture-editor/element-detail/components/BriefStatus";
import LinkList from "@/project/architecture-editor/element-detail/components/LinkList";
import WorkTab from "@/project/architecture-editor/element-detail/components/WorkTab";
import type { StudioElementView } from "../logic/element-view";
import "@/project/architecture-editor/element-detail/styles/element-detail.css";

/** Obsah Detailu prvku pod sebou, jen ke čtení (docs/studio.md §3): kontext agenta, Proč, Zadání, Práce a u komponenty
 * přímé vazby. Dílky jsou tytéž jako v Editoru stránky; bez callbacků nemají žádné ovládání, mění se v Editoru. */
export default function DetailElement({ view }: { view: StudioElementView }) {
  return <div className="studio-detail__element" data-testid="studio-detail-element">
    <AgentContextPanel context={view.context}/>
    {view.why && <p className="element-detail__why"><span className="element-detail__why-label">Proč</span> {view.why}</p>}
    <section className="studio-detail__section" aria-label="Zadání">
      <h3 className="studio-detail__heading">Zadání</h3>
      <div className="element-detail__pane"><BriefStatus spec={view.spec} phase={view.phase} done={view.done}/></div>
    </section>
    <section className="studio-detail__section" aria-label="Práce" data-testid="studio-detail-work">
      <h3 className="studio-detail__heading">Práce</h3>
      <WorkTab nodeId={view.nodeId} view={view.work}/>
    </section>
    {view.links && <section className="studio-detail__section" aria-label="Vazby" data-testid="studio-detail-element-links">
      <h3 className="studio-detail__heading">Vazby <span className="studio-detail__count">{view.links.incoming.length + view.links.outgoing.length}</span></h3>
      <div className="element-detail__pane">
        <LinkList title="Příchozí vazby" links={view.links.incoming} empty="Žádná příchozí vazba"/>
        <LinkList title="Odchozí vazby" links={view.links.outgoing} empty="Žádná odchozí vazba"/>
      </div>
    </section>}
  </div>;
}
