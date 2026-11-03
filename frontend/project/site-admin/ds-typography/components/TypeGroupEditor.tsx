import type { TypeGroup } from "@/project/site-admin/logic/site-document";
import TypeStyleRow from "./TypeStyleRow";

/** Skupina stylů: název, rodina a poznámka („Jedna rodina, čtyři kroky“) a pod nimi její styly. */
export default function TypeGroupEditor({ group, families, theme, canAddStyle, onChange, onAddStyle, onRemove }: {
  group: TypeGroup; families: string[]; theme: string; canAddStyle: boolean;
  onChange: (group: TypeGroup) => void; onAddStyle: () => void; onRemove: () => void;
}) {
  const field = (key: "name" | "family" | "note", value: string) => {
    const next: TypeGroup = { ...group };
    if (value === "" && key !== "name") delete next[key]; else next[key] = value;
    onChange(next);
  };
  return <section className="ds-type__group" aria-label={"Skupina " + group.name}>
    <div className="ds-type__group-head">
      <input className="ds-type__input ds-type__group-name" aria-label="Název skupiny" value={group.name} maxLength={64} onChange={(event) => field("name", event.target.value)}/>
      <select className="ds-type__input" aria-label="Rodina skupiny" value={group.family ?? ""} onChange={(event) => field("family", event.target.value)}>
        <option value="">bez rodiny</option>{families.map((key) => <option key={key} value={key}>{key}</option>)}
      </select>
      <input className="ds-type__input ds-type__input--wide" aria-label="Poznámka skupiny" placeholder="Poznámka (Jedna rodina, čtyři kroky)" value={group.note ?? ""} maxLength={400} onChange={(event) => field("note", event.target.value)}/>
      <button type="button" className="ds-type__remove" aria-label={"Odebrat skupinu " + group.name} onClick={onRemove}>×</button>
    </div>
    {group.styles.map((style, index) => <TypeStyleRow key={index} style={style} group={group} families={families} theme={theme}
      onChange={(next) => onChange({ ...group, styles: group.styles.map((item, at) => at === index ? next : item) })}
      onRemove={() => onChange({ ...group, styles: group.styles.filter((_, at) => at !== index) })}/>)}
    <button type="button" className="ds-type__add" disabled={!canAddStyle} onClick={onAddStyle}>+ Styl</button>
  </section>;
}
