import type { MouseEvent } from "react";
import { SECTION_ROLE_LABELS } from "../../../domain-site/logic/page-site";
import { childrenOf, type LayoutSection } from "../../layout-canvas/logic/layout-grid";
import { pageFlow } from "../logic/page-flow";
import "../styles/design-page.css";

type Props = {
  sections: LayoutSection[];
  /** Obrázek vzhledu boxu (id sekce → data URL, výřez ze skenu). */
  covers?: ReadonlyMap<string, string>;
  selectedBox?: string | null; onSelectBox?: (id: string) => void; onOpenBox?: (id: string) => void;
};

/** Pohled Design vrstvy 1: stránka v celku. Boxy jdou tokem shora dolů (`pageFlow`), výřez boxu celý bez ořezu,
 * mezi boxy jen tenká spára. Box s obrázkem ukáže obrázek (u rodiče obsahuje i děti), jinak kartu s popisem vzhledu,
 * a bez obrázku rodiče se děti kreslí stejným tokem uvnitř. Klik vybere, dvojklik otevře box; tah tu není. */
export default function DesignPage({ sections, covers, selectedBox, onSelectBox, onOpenBox }: Props) {
  const own = (handler?: (id: string) => void, id?: string) => (event: MouseEvent) => { event.stopPropagation(); if (id) handler?.(id); };
  const box = (section: LayoutSection, width: number, indent: number) => {
    const cover = covers?.get(section.id);
    const kids = cover ? [] : childrenOf(sections, section.id);
    return <div key={section.id} className={"design-page__box" + (cover ? " design-page__box--image" : "") + (selectedBox === section.id ? " design-page__box--selected" : "")}
      style={{ width: `${width * 100}%`, marginLeft: `${indent * 100}%` }} data-testid={"architecture-design-box-" + section.id}
      title={[section.name, section.intent, "Dvojklikem otevřete box"].filter(Boolean).join("\n")}
      onClick={own(onSelectBox, section.id)} onDoubleClick={own(onOpenBox, section.id)}>
      <span className="design-page__label">{section.name}<small className="design-page__role">{SECTION_ROLE_LABELS[section.role]}</small></span>
      {cover ? <img className="design-page__image" src={cover} alt={section.name} draggable={false}/>
        : !kids.length && <p className="design-page__look">{section.look || section.name}</p>}
      {kids.length > 0 && flow(kids)}
    </div>;
  };
  const flow = (boxes: LayoutSection[]) => <div className="design-page__flow">
    {pageFlow(boxes).map((row) => <div key={row.columns[0].items[0].id} className="design-page__row">
      {row.columns.flatMap((column, index) => [
        row.gaps[index] > 0 && <span key={"gap-" + column.start} className="design-page__gap" style={{ flexGrow: row.gaps[index] }}/>,
        <div key={column.start} className="design-page__column" style={{ flexGrow: column.span }}>
          {column.items.map((item) => box(item, item.box.w / column.span, (item.box.x - column.start) / column.span))}
        </div>])}
      {row.rest > 0 && <span className="design-page__gap" style={{ flexGrow: row.rest }}/>}
    </div>)}
  </div>;
  const top = childrenOf(sections, null);
  return <div className="design-page" data-testid="architecture-design-page">
    <p className="design-page__hint">Stránka v celku podle vzhledu boxů. Rozmístění boxů se mění v pohledu Layout.</p>
    {top.length ? <div className="design-page__paper">{flow(top)}</div>
      : <p className="design-page__empty">Stránka zatím nemá boxy. Poskládejte je v pohledu Layout, nebo převezměte sken webu.</p>}
  </div>;
}
