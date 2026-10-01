// Dílek Katalog: rozbalená knihovna postupů. Nahoře svislý seznam kategorií (řádek, ne čip — v úzkém
// panelu se čipy zalamovaly a nešlo je přečíst); prop `categories` ho omezí, aby si sekce Agenti a
// Postupy katalog rozdělily. Pod ním hledání a nadpis „Kategorie · N“, zbytek panelu je seznam řádků.
// Řádek ukáže účel a počet kroků (jen postup a pipeline kroky mají). Řádek je zdroj tažení (`startAgentDrag`); položka druhu `info`
// (hook, skill) se táhnout nedá a je ztlumená. Postup mimo profil projektu je ztlumený taky a pod
// popisem nese poznámku („mimo profil“ nebo „kvůli profilu: …“). Dílek nic nefiltruje a nic
// neukládá — kategorie, položky, počty, poznámky i filtr dostává hotové v props a změny hlásí nahoru.
//
// Všechny značky jsou kreslené ikony ze sady `ui-kit/icon`, ne Unicode glyfy: ikona řádku je ikona
// jeho kategorie (`categoryIcon`) — položka nese ikonu police, ve které leží, aby se oko po sloupci
// klouzalo místo aby ho zdržovalo devět různých znaků z katalogu.
import type { DragEvent, ReactNode } from "react";
import { categoryIcon, stepsBadge, stepsLine } from "@/layout/agent-navbar/logic/agent-navbar";
import Icon from "@/ui-kit/icon/components/Icon";
import {
  AGENT_CATEGORIES,
  startAgentDrag,
  type AgentCategory,
  type AgentItem,
} from "@/editor/component-library/agent-catalog/logic/agent-catalog";

const NO_NOTES: Readonly<Record<string, string>> = {};
const NO_OUTSIDE: ReadonlySet<string> = new Set();

export default function AgentNavbarCatalog({
  items,
  category,
  categoryCounts,
  notes = NO_NOTES,
  outside = NO_OUTSIDE,
  filter = null,
  footer = null,
  query,
  categories,
  onCategory,
  onSearch,
}: {
  /** Položky vybrané kategorie už po hledání; dílek je jen vypisuje. */
  items: AgentItem[];
  category: AgentCategory;
  /** Kolik položek má každá kategorie celkem (bez ohledu na hledání) — pro číslo u řádku kategorie. */
  categoryCounts: Record<AgentCategory, number>;
  /** „kvůli profilu: …“ nebo „mimo profil“ podle id položky. */
  notes?: Readonly<Record<string, string>>;
  outside?: ReadonlySet<string>;
  /** Přepínač „Pro tento projekt / Vše“ pod hledáním; skládá ho rodič. */
  filter?: ReactNode;
  /** Řádek „Mimo profil“ na konci seznamu; skládá ho rodič. */
  footer?: ReactNode;
  query: string;
  /** Které kategorie ukázat (id z `AGENT_CATEGORIES`); bez něj všechny. Sekce Agenti a Postupy si tak dělí katalog. */
  categories?: readonly string[];
  onCategory: (category: AgentCategory) => void;
  onSearch: (query: string) => void;
}) {
  const shown = categories ? AGENT_CATEGORIES.filter((item) => categories.includes(item.id)) : AGENT_CATEGORIES;
  const searchLabel = shown.some((item) => item.id === "workflows") ? "Najít postup" : "Najít agenta, skill nebo hook";
  const activeCategory = shown.find((item) => item.id === category) ?? shown[0] ?? AGENT_CATEGORIES[0];
  return (
    <div className="agent-navbar__catalog">
      <nav className="agent-navbar__categories" aria-label="Kategorie postupů">
        {shown.map((item) => (
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
          placeholder={searchLabel}
          aria-label={searchLabel}
          value={query}
          onChange={(event) => onSearch(event.target.value)}
        />
        <small className="agent-navbar__search-count">{items.length}</small>
      </div>
      {filter}

      <p className="agent-navbar__section-heading">{activeCategory.label} · {items.length}</p>

      <div className="agent-navbar__body">
        {items.length ? (
          <ul className={"agent-navbar__list agent-navbar__list--" + category}>
            {items.map((item) => {
              const draggable = item.kind !== "info";
              return (
                <li
                  key={item.id}
                  className={
                    "agent-navbar__item" +
                    (draggable ? "" : " agent-navbar__item--info") +
                    (outside.has(item.id) ? " agent-navbar__item--outside" : "")
                  }
                  draggable={draggable}
                  title={
                    item.purpose +
                    (item.steps?.length ? " — " + stepsLine(item.steps.length, (item.done ?? []).join("; ")) : "") +
                    (draggable ? " — táhněte na kartu nebo na plátno" : "")
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
                    <span className="agent-navbar__item-hint">{item.purpose}</span>
                    {notes[item.id] && <span className="agent-navbar__item-fit">{notes[item.id]}</span>}
                  </span>
                  {item.steps?.length ? <span className="agent-navbar__item-steps">{stepsBadge(item.steps.length)}</span> : null}
                  {draggable && <Icon className="agent-navbar__item-grip" name="grip-vertical" size={16} />}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="agent-navbar__empty">V téhle kategorii nic takového není. Zkuste jiné slovo.</p>
        )}
        {footer}
      </div>
    </div>
  );
}
