import { useContext, useEffect, useRef } from "react";
import type { CanvasNode, PageSection, PageSectionRole } from "@/shared/types/logic/types";
import { ProjectFlowsContext } from "@/project/project-flows/logic/project-flows-context";
import type { CardState } from "../../card-state/logic/card-state";
import { SECTION_ROLE_LABELS } from "../../domain-site/logic/page-site";
import { logicLook } from "../../page-editor/element-palette/logic/logic-groups";
import { boxSketchLayer, INTENT_MAX, STATUS_LABELS, statusOf } from "../logic/box-detail";
import BoxSketch from "./BoxSketch";
import BoxInspiration from "./BoxInspiration";
import "../styles/box-detail.css";

type Props = {
  project: string; workspace: string; pageId: string; section: PageSection;
  /** Prvky logiky boxu a jejich stav (Studio). */
  nodes: CanvasNode[]; states: ReadonlyMap<string, CardState>;
  /** Proč nejde měnit layout a stav (`structureLock`) a proč skica a inspirace (`contentLock`, Git main); `null` = jde. */
  layoutLock: string | null; contentLock: string | null;
  onChange: (patch: Partial<Omit<PageSection, "id">>) => void;
  /** Návrh: Přijmout = Schváleno, Zahodit = box pryč. */
  onDiscard: () => void;
  onSelectElement: (id: string) => void; onClose: () => void;
  /** Skica se uložila; rodič obnoví značky boxů. */
  onSketchSaved: () => void;
  /** `false` = skicu kreslí zanořený pohled boxu na ploše; druhé kreslení nad stejnou vrstvou by si přepisovalo draft. */
  sketch?: boolean;
};

/** Detail boxu v pravém sloupci plátna 2: název, role, záměr, stav (Rozpracováno / Návrh / Schváleno), skica, inspirace
 * a prvky logiky boxu. Klik na prvek otevře Detail prvku, dvojklik jeho plátno logiky. Dílek nic neukládá: změny hlásí `onChange`. */
export default function BoxDetail(props: Props) {
  const { section, layoutLock, contentLock } = props;
  const status = statusOf(section);
  const locked = !!layoutLock;
  const { onOpenLogic } = useContext(ProjectFlowsContext);
  // Klik přepne sloupec na Detail prvku a řádek zmizí, takže by druhý klik dvojkliku nikdy nedošel: výběr počká na dvojklik.
  const pending = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(pending.current), []);
  const select = (id: string) => { window.clearTimeout(pending.current); pending.current = window.setTimeout(() => props.onSelectElement(id), 250); };
  const open = (node: CanvasNode) => { window.clearTimeout(pending.current); onOpenLogic?.(node); };
  return <div className="box-detail" data-testid="architecture-box-detail">
    <header className="box-detail__head">
      <h3 className="box-detail__title">Detail boxu</h3>
      <button type="button" className="box-detail__close" aria-label="Zavřít detail boxu" onClick={props.onClose}>✕</button>
    </header>
    <label className="box-detail__field">Název
      <input key={section.name} defaultValue={section.name} maxLength={60} disabled={locked} data-testid="architecture-box-name"
        onBlur={(event) => { const value = event.target.value.trim(); if (value) props.onChange({ name: value }); else event.target.value = section.name; }}/></label>
    <label className="box-detail__field">Role
      <select value={section.role} disabled={locked} onChange={(event) => props.onChange({ role: event.target.value as PageSectionRole })}>
        {Object.entries(SECTION_ROLE_LABELS).map(([role, label]) => <option key={role} value={role}>{label}</option>)}
      </select></label>
    <label className="box-detail__field">Záměr
      <textarea key={section.intent} defaultValue={section.intent} rows={3} maxLength={INTENT_MAX} disabled={locked} placeholder="Co má box u návštěvníka udělat"
        onBlur={(event) => props.onChange({ intent: event.target.value.trim() })}/></label>
    <section className="box-detail__block" aria-label="Stav">
      <h4 className="box-detail__block-title">Stav <span className={"box-detail__status box-detail__status--" + status} data-testid="architecture-box-status">{STATUS_LABELS[status]}</span>
        {section.source && <small className="box-detail__source">zapsal {section.source === "human" ? "člověk" : section.source === "agent" ? "agent" : "sken"}</small>}</h4>
      <div className="box-detail__actions">
        {status === "proposed" && <>
          <button type="button" className="box-detail__action box-detail__action--primary" disabled={locked} data-testid="architecture-box-accept" onClick={() => props.onChange({ status: "approved" })}>Přijmout</button>
          <button type="button" className="box-detail__action" disabled={locked} data-testid="architecture-box-discard" onClick={props.onDiscard}>Zahodit</button></>}
        {status === "draft" && <button type="button" className="box-detail__action" disabled={locked} onClick={() => props.onChange({ status: "approved" })}>Schválit</button>}
        {status === "approved" && <button type="button" className="box-detail__action" disabled={locked} onClick={() => props.onChange({ status: "draft" })}>Vrátit do rozpracování</button>}
      </div>
      {layoutLock && <p className="box-detail__hint">{layoutLock}</p>}
    </section>
    {props.sketch !== false && <BoxSketch project={props.project} workspace={props.workspace} layer={boxSketchLayer(props.pageId, section.id)} title={section.name} lock={contentLock} onSaved={props.onSketchSaved}/>}
    <BoxInspiration project={props.project} workspace={props.workspace} inspiration={section.inspiration} lock={contentLock} onChange={(inspiration) => props.onChange({ inspiration })}/>
    <section className="box-detail__block" aria-label="Prvky logiky">
      <h4 className="box-detail__block-title">Prvky logiky <small>{props.nodes.length}</small></h4>
      {props.nodes.length ? <ul className="box-detail__logic">
        {props.nodes.map((node) => { const look = node.element ? logicLook(node.element.kind) : { label: "Prvek" }; const state = props.states.get(node.id);
          return <li key={node.id}><button type="button" className="box-detail__logic-item" title="Dvojklikem plátno logiky" onClick={() => select(node.id)} onDoubleClick={() => open(node)}>
            <span className="box-detail__logic-kind">{look.label}</span> {node.name}{state && <small className="box-detail__logic-state"> · {state.label}</small>}</button></li>; })}
      </ul> : <p className="box-detail__hint">Box zatím nemá prvky logiky. Vložte je ve vrstvě 2 Logika.</p>}
    </section>
  </div>;
}
