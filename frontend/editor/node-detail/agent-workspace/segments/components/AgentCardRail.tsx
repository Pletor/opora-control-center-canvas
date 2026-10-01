// Levá lišta karet: vrstva a její děti pod sebou, jedna z nich je vybraná a její segmenty se
// kreslí vpravo. Lišta nic nenačítá — jména a druhy dostává hotové od desky a každý klik hlásí
// nahoru. „Zanořit“ zůstává u dětí ve stejné roli jako v dokumentu: přepne celou plochu o patro níž.
import "@/editor/node-detail/agent-workspace/segments/styles/agent-segments.css";

export type RailCard = {
  id: string;
  name: string;
  /** Popisek druhu tak, jak ho člověk čte na plátně: Vrstva, Sektor, Uzel, Oblast, Poznámka. */
  kindLabel: string;
  /** Do vrstvy, ve které právě stojím, se zanořit nedá; do dítěte ano. */
  enterable: boolean;
};

export default function AgentCardRail({
  cards,
  selected,
  onSelect,
  onEnter,
}: {
  cards: RailCard[];
  selected: string;
  onSelect: (id: string) => void;
  onEnter: (id: string) => void;
}) {
  return (
    <nav className="agent-segments__rail" aria-label="Karty vrstvy">
      <p className="agent-segments__rail-title">Karty</p>
      <ul className="agent-segments__rail-list">
        {cards.map((card) => (
          <li
            key={card.id}
            className={"agent-segments__rail-item" + (card.id === selected ? " agent-segments__rail-item--selected" : "")}
          >
            <button
              type="button"
              className="nodrag agent-segments__rail-pick"
              aria-pressed={card.id === selected}
              onClick={() => onSelect(card.id)}
            >
              <span className="agent-segments__rail-kind">{card.kindLabel}</span>
              <span className="agent-segments__rail-name">{card.name}</span>
            </button>
            {card.enterable && (
              <button type="button" className="nodrag agent-segments__rail-enter" onClick={() => onEnter(card.id)}>
                Zanořit
              </button>
            )}
          </li>
        ))}
      </ul>
      {!cards.length && <p className="agent-segments__rail-empty muted">Tato vrstva nemá žádnou kartu.</p>}
    </nav>
  );
}
