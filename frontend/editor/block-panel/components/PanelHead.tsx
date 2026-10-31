// Hlavička panelu podle návrhu: v jedné řádce druh (KARTA / BLOK n), pořadí karty podle záměru, krátké ID
// a zavírací ×. Pod tím název (u bloku název bloku a „karta …“), popis nebo účel karty, obojí jen ke čtení
// (píše se na kartě v plátně), a jedna tichá řádka poslední změny karty „kdo · kdy · co“.
import type { PanelView } from "../logic/panel-view";

export default function PanelHead({ head, onClose }: { head: PanelView["head"]; onClose?: () => void }) {
  const card = head.kind === "card";
  return (
    <header className="block-panel__head">
      <div className="block-panel__toprow">
        <span className="block-panel__kind">{card ? "KARTA" : `BLOK ${head.number}`}</span>
        {head.order && <span className="block-panel__order" title="Pořadí karty podle záměru">{head.order}</span>}
        <code className="block-panel__id" title={`ID ${card ? "karty" : "bloku"} ${head.id}`}>{head.id.slice(0, 8)}</code>
        {onClose && <button type="button" className="block-panel__close" aria-label="Zavřít panel karty" title="Zavřít" onClick={onClose}>×</button>}
      </div>
      <h2 className="block-panel__title">{head.title}</h2>
      {!card && <p className="block-panel__card">karta {head.cardName}</p>}
      {head.text.trim() && <p className="block-panel__desc">{head.text}</p>}
      {head.change && <div className="block-panel__change" data-oh-last-change-who={head.change.whoKind}>
        <b className={"block-panel__change-who block-panel__change-who--" + head.change.whoKind}>{head.change.who}</b>
        {[head.change.when, head.change.what].filter(Boolean).map((part) => " · " + part).join("")}
      </div>}
    </header>
  );
}
