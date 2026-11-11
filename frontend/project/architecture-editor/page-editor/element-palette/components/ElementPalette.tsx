import type { PointerEvent } from "react";
import type { ElementKind } from "@/shared/types/logic/types";
import { LOGIC_GROUPS } from "../logic/logic-groups";
import PageIcon from "../../components/PageIcon";
import "../styles/element-palette.css";

type Props = {
  disabled: boolean;
  /** Klik vloží prvek na celou stránku; stisk začne tah do boxu nebo na pruh Celá stránka (`useCarry` u rodiče). */
  onInsert: (kind: ElementKind, label: string) => void; onCarry: (kind: ElementKind, label: string, event: PointerEvent) => void;
};

/** Paleta vrstvy Logika: otázky člověka (Kdo, Kdo smí, Co musí splnit, Co se děje, S čím, Napojení) a pod každou druhy česky.
 * Nic neukládá; vložení i tah hlásí rodiči. */
export default function ElementPalette({ disabled, onInsert, onCarry }: Props) {
  return <section className="element-palette" aria-label="Prvky logiky">
    <h3 className="element-palette__title">Prvky logiky</h3>
    {LOGIC_GROUPS.map((group) => <div key={group.question} className="element-palette__group">
      <span className="element-palette__question"><PageIcon name={group.icon} size={15} className="element-palette__icon"/>{group.question}</span>
      <div className="element-palette__kinds">
        {group.kinds.map(({ kind, label }) => <button key={kind} type="button" className="element-palette__kind" disabled={disabled} data-testid={"architecture-insert-" + kind}
          onPointerDown={(event) => onCarry(kind, label, event)} onClick={() => onInsert(kind, label)}>{label}</button>)}
      </div>
    </div>)}
  </section>;
}
