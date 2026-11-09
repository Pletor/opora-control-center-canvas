import { ELEMENT_GROUPS, ELEMENT_LABELS } from "@/editor/canvas/create-dialog/logic/element-palette";
import type { ElementKind } from "@/shared/types/logic/types";

export default function ElementKindField({ value, disabled, onChange }: {
  value: ElementKind | ""; disabled?: boolean; onChange: (kind: ElementKind | "") => void;
}) {
  return <label className="field">Druh prvku aplikace
    <select aria-label="Druh prvku aplikace" value={value} disabled={disabled}
      onChange={event => onChange(event.target.value as ElementKind | "")}>
      <option value="">Neurčeno</option>
      {ELEMENT_GROUPS.map(group => <optgroup key={group.label} label={group.label}>
        {group.kinds.map(kind => <option key={kind} value={kind}>{ELEMENT_LABELS[kind]}</option>)}
      </optgroup>)}
    </select>
  </label>;
}
