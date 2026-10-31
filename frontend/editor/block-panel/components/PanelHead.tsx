// Hlavička panelu: číslo bloku, pořadí karty podle záměru, ID, název a popis bloku (jen ke čtení: píše se
// na kartě v plátně) a jedna tichá řádka poslední změny karty „kdo · kdy · co“.
import type { PanelView } from "../logic/panel-view";

export default function PanelHead({ head }: { head: PanelView["head"] }) {
  return (
    <header className="block-panel__head">
      <div className="block-panel__toprow">
        <span className="block-panel__kind">BLOK {head.number}</span>
        {head.order && <span className="block-panel__order" title="Pořadí karty podle záměru">{head.order}</span>}
        <code className="block-panel__id" title={`ID bloku ${head.blockId}`}>{head.blockId.slice(0, 8)}</code>
      </div>
      <h2 className="block-panel__title">{head.title}</h2>
      <p className="block-panel__card">karta {head.cardName}</p>
      {head.text.trim() && <p className="block-panel__desc">{head.text}</p>}
      {head.change && <div className="block-panel__change" data-oh-last-change-who={head.change.whoKind}>
        <b className={"block-panel__change-who block-panel__change-who--" + head.change.whoKind}>{head.change.who}</b>
        {[head.change.when, head.change.what].filter(Boolean).map((part) => " · " + part).join("")}
      </div>}
    </header>
  );
}
