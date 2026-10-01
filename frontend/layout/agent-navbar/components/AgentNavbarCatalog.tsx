// Dílek Katalog: rozbalená knihovna postupů. Nahoře svislý seznam šesti kategorií (řádek, ne
// čip — v úzkém panelu se čipy zalamovaly a nešlo je přečíst), pod ním hledání a nadpis „Kategorie ·
// N“, zbytek panelu je seznam řádků. Řádek je zdroj tažení (`startAgentDrag`); položka druhu `info`
// (hook, skill) se táhnout nedá a je ztlumená. Dílek nic nefiltruje a nic neukládá — kategorie,
// položky i jejich počty dostává hotové v props a změny hlásí nahoru.
//
// Všechny značky jsou kreslené ikony ze sady `ui-kit/icon`, ne Unicode glyfy: ikona řádku je ikona
// jeho kategorie (`categoryIcon`) — položka nese ikonu police, ve které leží, aby se oko po sloupci
// klouzalo místo aby ho zdržovalo devět různých znaků z katalogu.
import type { DragEvent } from "react";
import { categoryIcon, stepsBadge, stepsLine } from "@/layout/agent-navbar/logic/agent-navbar";
import Icon from "@/ui-kit/icon/components/Icon";
import {
  AGENT_CATEGORIES,
  startAgentDrag,
  type AgentCategory,
  type AgentItem,
} from "@/editor/component-library/agent-catalog/logic/agent-catalog";

export default function AgentNavbarCatalog({
  items,
  category,
  categoryCounts,
  query,
  onCategory,
  onSearch,
}: {
  /** Položky vybrané kategorie už po hledání; dílek je jen vypisuje. */
  items: AgentItem[];
  category: AgentCategory;
  /** Kolik položek má každá kategorie celkem (bez ohledu na hledání) — pro číslo u řádku kategorie. */
  categoryCounts: Record<AgentCategory, number>;
  query: string;
  onCategory: (category: AgentCategory) => void;
  onSearch: (query: string) => void;
}) {
  const activeCategory = AGENT_CATEGORIES.find((item) => item.id === category) ?? AGENT_CATEGORIES[0];
  return (
    <div className="agent-navbar__catalog">
      <nav className="agent-navbar__categories" aria-label="Kategorie postupů">
        {AGENT_CATEGORIES.map((item) => (
          <button
            key={item.id}
            type="button"
            className={
              "agent-navbar__category agent-navbar__category--" +
              item.id +
              (category === item.id ? " agent-navbar__category--active" : "")
            }
            aria-pressed={category === item.id}
            title={item.label + " — " + item.hint}
            data-testid={"agent-category-" + item.id}
            onClick={() => onCategory(item.id)}
          >
            <span className="agent-navbar__category-icon">
              <Icon name={categoryIcon(item.id)} size={16} />
            </span>
            <span className="agent-navbar__category-label">{item.label}</span>
            <span className="agent-navbar__category-count">{categoryCounts[item.id] ?? 0}</span>
          </button>
        ))}
      </nav>

      <div className="agent-navbar__search">
        <Icon className="agent-navbar__search-icon" name="search" size={16} />
        <input
          type="search"
          className="agent-navbar__search-input"
          placeholder="Najít postup"
          aria-label="Najít postup"
          value={query}
          onChange={(event) => onSearch(event.target.value)}
        />
        <small className="agent-navbar__search-count">{items.length}</small>
      </div>

      <p className="agent-navbar__section-heading">{activeCategory.label} · {items.length}</p>

      <div className="agent-navbar__body">
        {items.length ? (
          <ul className={"agent-navbar__list agent-navbar__list--" + category}>
            {items.map((item) => {
              const draggable = item.kind !== "info";
              return (
                <li
                  key={item.id}
                  className={"agent-navbar__item" + (draggable ? "" : " agent-navbar__item--info")}
                  draggable={draggable}
                  title={
                    item.hint +
                    " — " +
                    stepsLine(item.decomposition.length, item.endCriteria) +
                    (draggable ? " — chyťte a táhněte na plátno" : "")
                  }
                  data-testid={"agent-tile-" + item.id}
                  onDragStart={(event: DragEvent<HTMLLIElement>) => {
                    if (draggable) startAgentDrag(event.dataTransfer, item.id);
                    else event.preventDefault();
                  }}
                >
                  <span className="agent-navbar__item-icon">
                    <Icon name={categoryIcon(category)} size={16} />
                  </span>
                  <span className="agent-navbar__item-text">
                    <span className="agent-navbar__item-name">{item.label}</span>
                    <span className="agent-navbar__item-hint">{item.hint}</span>
                  </span>
                  <span className="agent-navbar__item-steps">{stepsBadge(item.decomposition.length)}</span>
                  {draggable && <Icon className="agent-navbar__item-grip" name="grip-vertical" size={16} />}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="agent-navbar__empty">V téhle kategorii nic takového není. Zkuste jiné slovo.</p>
        )}
      </div>
    </div>
  );
}
