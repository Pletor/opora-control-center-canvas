import type { ReactNode } from "react";
import type { StudioDetailView } from "../logic/detail-model";
import DetailSections from "./DetailSections";
import "../styles/studio-detail.css";

/** Panel detailu vpravo, jako Inspector v TechViz (ve Skutečnosti jen čtení): identita karty (druh, název, adresa, stav),
 * účel, souhrn, vazby, díry, cesty a odkaz do Architektury projektu. Bez výběru ukazuje otevřenou úroveň. Pod obsahem
 * smí rodič přidat panel (`extra`), např. dráhy cest domény. Akce hlásí rodiči (`onOpenEditor`, `onClear`). */
export default function StudioDetail({ view, selected, onOpenEditor, onClear, extra }: {
  view: StudioDetailView | null; selected: boolean; onOpenEditor: (params: Record<string, string>) => void; onClear: () => void; extra?: ReactNode;
}) {
  return <aside className="studio-detail" aria-label="Detail Studia" data-testid="studio-detail">
    <header className="studio-detail__title">
      <span>{selected ? "Detail karty" : "Otevřená úroveň"}</span>
      {selected && <button type="button" className="studio-detail__clear" onClick={onClear} title="Zrušit výběr (Escape)">×</button>}
    </header>
    {!view ? <p className="studio-detail__empty">Projekt: vyberte doménu na plátně, dvojklikem do ní vstoupíte.</p> : <>
      <section className={`studio-detail__identity studio-detail__identity--${view.state}`}>
        <small className="studio-detail__kind">{view.kindLabel}</small>
        <h2 className="studio-detail__name" data-testid="studio-detail-name">{view.name}</h2>
        {view.subtitle && <code className="studio-detail__subtitle">{view.subtitle}</code>}
        <div className="studio-detail__facts">
          <span className="studio-detail__state" data-testid="studio-detail-state">{view.stateLabel}</span>
          <span className="studio-detail__summary">{view.summary}</span>
        </div>
        {view.editor && <button type="button" className="studio-detail__editor" data-testid="studio-open-editor" onClick={() => onOpenEditor(view.editor!.params)}>{view.editor.label}</button>}
      </section>
      <p className="studio-detail__purpose">{view.purpose || "Účel zatím nikdo nenapsal."}</p>
      <DetailSections view={view}/>
    </>}
    {extra}
  </aside>;
}
