import { useState } from "react";
import type { Theme } from "@/project/site-admin/logic/site-document";
import { MAX_THEMES } from "../logic/color-themes";

/** Témata barev: název jde přepsat na místě, šipky mění pořadí (první je výchozí), × téma odebere. */
export default function ThemeBar({ themes, onAdd, onRename, onMove, onRemove }: {
  themes: Theme[]; onAdd: (name: string) => void; onRename: (id: string, name: string) => void;
  onMove: (id: string, step: number) => void; onRemove: (id: string) => void;
}) {
  const [name, setName] = useState("");
  const add = () => { if (name.trim()) { onAdd(name); setName(""); } };
  return <div className="ds-colors__themes" aria-label="Témata barev">
    {themes.map((theme, index) => <span key={theme.id} className={"ds-colors__theme" + (index === 0 ? " ds-colors__theme--first" : "")}>
      <input className="ds-colors__theme-name" aria-label={"Název tématu " + theme.id} value={theme.name} maxLength={64}
        onChange={(event) => onRename(theme.id, event.target.value)}/>
      <code className="ds-colors__theme-id">{index === 0 ? theme.id + " · výchozí" : theme.id}</code>
      <button type="button" className="ds-colors__icon" aria-label={"Posunout " + theme.name + " doleva"} disabled={index === 0} onClick={() => onMove(theme.id, -1)}>‹</button>
      <button type="button" className="ds-colors__icon" aria-label={"Posunout " + theme.name + " doprava"} disabled={index === themes.length - 1} onClick={() => onMove(theme.id, 1)}>›</button>
      <button type="button" className="ds-colors__icon" aria-label={"Odebrat téma " + theme.name} disabled={themes.length <= 1} onClick={() => onRemove(theme.id)}>×</button>
    </span>)}
    {themes.length < MAX_THEMES && <form className="ds-colors__theme-add" onSubmit={(event) => { event.preventDefault(); add(); }}>
      <input className="ds-colors__theme-name" aria-label="Nové téma" placeholder="Nové téma (Dark…)" value={name} maxLength={64} onChange={(event) => setName(event.target.value)}/>
      <button type="submit" className="ds-colors__add" disabled={!name.trim()}>+ Téma</button>
    </form>}
  </div>;
}
