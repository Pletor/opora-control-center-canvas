import { useMemo, useState } from "react";
import type { NodeTypeSpec } from "../../logic/flow-types";
import { KIND_LABEL } from "../../logic/node-role";
import { PALETTE_DRAG_TYPE, paletteGroups, type PaletteItem, type PortFilter } from "../logic/palette";
import IntentWizard from "./IntentWizard";
import "../styles/node-palette.css";

/** Tooltip položky: kdy typ použít a kdy ne (z registru). */
const tip = (item: PaletteItem) => [item.use && `Kdy použít: ${item.use}`, item.avoid && `Kdy ne: ${item.avoid}`].filter(Boolean).join(" · ") || undefined;

type Props = { types: readonly NodeTypeSpec[]; port: PortFilter | null; onPick: (type: string) => void; onClearPort: () => void; onClose: () => void };

/** Šuplík „Co bude dál?“: průvodce „Co chci udělat?“ (`IntentWizard`), hledání a kategorie z registru typů. Otevřený z „+“ u portu ukáže jen typy s kompatibilním
 * portem a štítek, ke kterému portu se přidává. Klik přidá uzel, tah ho pustí na místo na plátně. */
export default function NodePalette({ types, port, onPick, onClearPort, onClose }: Props) {
  const [query, setQuery] = useState(""), [wizard, setWizard] = useState(false);
  const groups = useMemo(() => paletteGroups(types, query, port), [types, query, port]);
  return <aside className="node-palette" aria-label="Paleta uzlů" data-testid="node-palette">
    <header className="node-palette__head">
      <h3 className="node-palette__title">Co bude dál?</h3>
      <button type="button" className="node-palette__close" aria-label="Zavřít paletu" onClick={onClose}>×</button>
    </header>
    {port && <p className="node-palette__port">k portu <b>{KIND_LABEL[port.kind]}</b> ({port.direction === "in" ? "vstup" : "výstup"})
      <button type="button" className="node-palette__port-clear" onClick={onClearPort}>všechny typy</button></p>}
    {types.some((spec) => spec.intents?.length) && <button type="button" className="node-palette__ask" data-testid="intent-open" onClick={() => setWizard(true)}>Co chci udělat?</button>}
    {wizard && <IntentWizard types={types} onPick={(type) => { setWizard(false); onPick(type); }} onClose={() => setWizard(false)}/>}
    <input className="node-palette__search" autoFocus placeholder="Hledat uzly…" aria-label="Hledat uzly" value={query} onChange={(event) => setQuery(event.target.value)}/>
    {!groups.length && <p className="node-palette__empty">{port && !query ? "Registr zatím nemá typ s tímto portem." : "Nic neodpovídá."}</p>}
    {groups.map((group) => <section key={group.id} className="node-palette__group">
      <h4 className="node-palette__group-title">{group.label}</h4>
      {group.items.map((item) => <button key={item.type} type="button" className="node-palette__item" draggable data-testid={`palette-${item.type}`}
        onDragStart={(event) => { event.dataTransfer.setData(PALETTE_DRAG_TYPE, item.type); event.dataTransfer.effectAllowed = "copy"; }}
        title={tip(item)} onClick={() => onPick(item.type)}>
        <span className="node-palette__glyph" aria-hidden="true">{item.glyph}</span>
        <span className="node-palette__text"><b className="node-palette__name">{item.name}</b><small className="node-palette__summary">{item.family} · {item.summary}</small></span>
      </button>)}
    </section>)}
  </aside>;
}
