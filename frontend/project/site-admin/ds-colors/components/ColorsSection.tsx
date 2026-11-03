import { useState } from "react";
import type { ColorFamily } from "@/project/site-admin/logic/site-document";
import { freeName, nameProblem } from "@/project/site-admin/logic/token-names";
import { addTheme, moveTheme, removeTheme, renameTheme } from "../logic/color-themes";
import { colorGroups, removeToken, renameColor, replaceToken } from "../logic/color-tokens";
import ThemeBar from "./ThemeBar";
import ColorTokenRow, { rowColumns } from "./ColorTokenRow";
import "../styles/ds-colors.css";

/** Colors: témata nahoře, pod nimi barvy seskupené podle kmene jména (`bg-100` → `bg`). Dílek dostane rodinu barev
 *  a jména celého systému (sdílený jmenný prostor) a každou změnu hlásí celou rodinou nahoru. */
export default function ColorsSection({ family, taken, onChange }: { family: ColorFamily; taken: string[]; onChange: (family: ColorFamily) => void }) {
  const [name, setName] = useState("");
  const problem = name ? nameProblem(name, taken) : "";
  const add = () => {
    const next = name.trim() || freeName("color", taken);
    if (nameProblem(next, taken)) return;
    onChange({ ...family, tokens: [...family.tokens, { name: next, value: "#888888" }] });
    setName("");
  };
  const tokens = family.tokens;
  return <div className="ds-colors">
    <ThemeBar themes={family.themes} onAdd={(theme) => onChange(addTheme(family, theme))} onRename={(id, theme) => onChange(renameTheme(family, id, theme))}
      onMove={(id, step) => onChange(moveTheme(family, id, step))} onRemove={(id) => onChange(removeTheme(family, id))}/>
    <form className="ds-colors__add-row" onSubmit={(event) => { event.preventDefault(); add(); }}>
      <input className="ds-colors__name-input" aria-label="Jméno nové barvy" placeholder="jméno nové barvy (ink, bg-100, on-brand…)" value={name} maxLength={64} spellCheck={false} onChange={(event) => setName(event.target.value)}/>
      <button type="submit" className="ds-colors__add" disabled={!!problem}>+ Barva</button>
      {problem && <small className="ds-colors__problem" role="alert">{problem}</small>}
    </form>
    {!tokens.length && <p className="ds-colors__empty">Zatím žádné barvy. Začni podkladem <code>surface</code>, textem <code>ink</code> a hlavní barvou s dvojicí <code>on-…</code> pro text na ní.</p>}
    {!!tokens.length && <div className="ds-colors__header" aria-hidden="true" style={{ gridTemplateColumns: rowColumns(family.themes.length) }}>
      <span>Jméno</span>{family.themes.map((theme, index) => <span key={theme.id}>{theme.name}{index === 0 ? " · výchozí" : ""}</span>)}<span>Kdy použít</span><span/>
    </div>}
    {colorGroups(tokens).map((group) => <section key={group.stem} className="ds-colors__group" aria-label={"Skupina " + group.stem}>
      <h4 className="ds-colors__group-title">{group.stem}</h4>
      {group.items.map(({ token, index }) => <ColorTokenRow key={index + ":" + token.name} family={family} token={token} taken={taken}
        onChange={(next) => onChange({ ...family, tokens: replaceToken(tokens, index, next) })}
        onRename={(next) => onChange({ ...family, tokens: renameColor(tokens, index, next) })}
        onRemove={() => onChange({ ...family, tokens: removeToken(tokens, index) })}/>)}
    </section>)}
  </div>;
}
