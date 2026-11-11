import type { PointerEvent } from "react";
import { BOX_KINDS, TEMPLATES } from "../../layout-canvas/logic/layout-templates";
import type { BoxKind } from "../../layout-canvas/logic/layout-edit";
import PageIcon from "../../components/PageIcon";
import "../styles/box-palette.css";

type Props = {
  disabled: boolean;
  /** Klik přidá box na konec stránky; stisk začne tah na plátno (`useCarry` u rodiče). */
  onAdd: (box: BoxKind) => void; onCarry: (box: BoxKind, event: PointerEvent) => void;
  onTemplate: (id: string) => void;
};

/** Paleta vrstvy Layout: boxy stránky a tři šablony. Nic neukládá; vše hlásí rodiči. */
export default function BoxPalette({ disabled, onAdd, onCarry, onTemplate }: Props) {
  return <section className="box-palette" aria-label="Boxy layoutu">
    <h3 className="box-palette__title">Boxy</h3>
    <div className="box-palette__boxes">
      {BOX_KINDS.map((box) => <button key={box.role} type="button" className={"box-palette__box box-palette__box--" + box.role} disabled={disabled}
        data-testid={"architecture-box-kind-" + box.role} onPointerDown={(event) => onCarry(box, event)} onClick={() => onAdd(box)}>{box.name}</button>)}
    </div>
    <h3 className="box-palette__title">Šablony</h3>
    {TEMPLATES.map((template) => <button key={template.id} type="button" className="box-palette__template" disabled={disabled}
      data-testid={"architecture-template-" + template.id} onClick={() => onTemplate(template.id)}>
      <PageIcon name="layout" size={16} className="box-palette__icon"/>
      <span className="box-palette__template-text"><strong>{template.name}</strong><small>{template.note}</small></span>
    </button>)}
  </section>;
}
