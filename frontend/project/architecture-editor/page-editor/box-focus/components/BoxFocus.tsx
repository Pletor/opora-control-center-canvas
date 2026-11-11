import { useEffect } from "react";
import { SECTION_ROLE_LABELS } from "../../../domain-site/logic/page-site";
import { boxSketchLayer } from "../../../box-detail/logic/box-detail";
import { childrenOf, type LayoutSection } from "../../layout-canvas/logic/layout-grid";
import { focusPath } from "../logic/box-focus";
import BoxFocusSketch from "./BoxFocusSketch";
import "../styles/box-focus.css";

type Props = {
  project: string; workspace: string; pageId: string; pageName: string;
  sections: LayoutSection[]; focusId: string;
  /** Box, jehož Detail je vpravo (klik na vnořený box ho vybere). */
  selectedBox: string | null;
  /** Proč kresbu nejde měnit (zámek obsahu: Git main, kompletní stránka); `null` = jde. */
  lock: string | null | undefined;
  onOpen: (id: string) => void; onSelectBox: (id: string) => void;
  /** `null` = zpět na layout stránky. */
  onLeave: (parentId: string | null) => void;
  onSketchSaved: () => void;
};

/** Zanořený pohled boxu přes celou plochu plátna: drobečky Stránka › Box › vnořený box s návratem, vlevo vnořené boxy
 * (klik vybere, dvojklik zanoří dál), uprostřed velká kresba skici boxu. Detail boxu vpravo skládá rodič. Esc mimo
 * kreslení, pole a okna vrátí o úroveň výš. Dílek nic neukládá; kresbu ukládá samo kreslení. */
export default function BoxFocus(props: Props) {
  const path = focusPath(props.sections, props.focusId);
  const box = path[path.length - 1];
  const up = path.length > 1 ? path[path.length - 2].id : null;
  const { onLeave } = props;
  useEffect(() => {
    const leave = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || document.querySelector("dialog[open], .box-detail__zoom, .box-detail__modal")) return;
      if (event.target instanceof Element && event.target.closest(".excalidraw, input, textarea, select, .box-detail__zoom")) return;
      onLeave(up);
    };
    window.addEventListener("keydown", leave);
    return () => window.removeEventListener("keydown", leave);
  }, [onLeave, up]);
  if (!box) return null;
  const kids = childrenOf(props.sections, box.id);
  return <div className="box-focus" data-testid="architecture-box-focus">
    <nav className="box-focus__crumbs" aria-label="Zanoření boxu">
      <button type="button" className="box-focus__back" data-testid="architecture-box-focus-back" onClick={() => onLeave(null)}>← Zpět na layout</button>
      <button type="button" className="box-focus__crumb" onClick={() => onLeave(null)}>{props.pageName}</button>
      {path.map((item) => <span key={item.id} className="box-focus__step">›
        {item.id === box.id ? <strong className="box-focus__crumb box-focus__crumb--current" aria-current="location">{item.name}</strong>
          : <button type="button" className="box-focus__crumb" onClick={() => props.onOpen(item.id)}>{item.name}</button>}</span>)}
      <small className="box-focus__esc">Esc o úroveň výš</small>
    </nav>
    <div className="box-focus__body">
      <section className="box-focus__nested" aria-label="Vnořené boxy">
        <h4 className="box-focus__nested-title">Vnořené boxy <small>{kids.length}</small></h4>
        {kids.length ? <ul className="box-focus__list">
          {kids.map((kid) => <li key={kid.id}><button type="button" className="box-focus__kid" aria-pressed={props.selectedBox === kid.id}
            title="Dvojklikem otevřete box" data-testid={"architecture-box-focus-kid-" + kid.id} onClick={() => props.onSelectBox(kid.id)} onDoubleClick={() => props.onOpen(kid.id)}
            onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); props.onOpen(kid.id); } }}>
            <span className="box-focus__kid-name">{kid.name}</span> <small className="box-focus__kid-role">{SECTION_ROLE_LABELS[kid.role]}</small></button></li>)}
        </ul> : <p className="box-focus__hint">Box nemá vnořené boxy. Ve vrstvě Layout je vložíte puštěním boxu do tohoto boxu.</p>}
      </section>
      <BoxFocusSketch key={box.id} project={props.project} workspace={props.workspace} layer={boxSketchLayer(props.pageId, box.id)} title={box.name}
        inspiration={box.inspiration?.files ?? []} lock={props.lock} onSaved={props.onSketchSaved}/>
    </div>
  </div>;
}
