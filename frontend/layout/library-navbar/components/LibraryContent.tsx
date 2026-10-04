// Dílek OBSAH: jeden seznam prvků podle kategorií (docs/menu-a-katalog.md §B1). Každý prvek je v něm
// právě jednou. Řádek nese popisek a účel, je zdrojem tažení na plátno a klik na něj otevře pod ním
// náhled (`LibraryItemDetail`). Kategorie, které jsou ve výběru jen kvůli profilu, stojí nahoře se
// štítkem; prvek mimo profil je ztlumený. Dílek nic nefiltruje ani neukládá: kategorie, prvky,
// poznámky i otevřený prvek dostává hotové a klik hlásí `onOpen` nahoru.
import type { DragEvent } from "react";
import { categoryIcon, startCatalogDrag } from "@/layout/library-navbar/logic/library-navbar";
import LibraryItemDetail from "@/layout/library-navbar/components/LibraryItemDetail";
import Icon from "@/ui-kit/icon/components/Icon";
import type { CatalogCategoryInfo, CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { CATALOG_FAMILIES } from "@/editor/component-library/library-catalog/logic/catalog-families";

const NO_NOTES: Readonly<Record<string, string>> = {};
const NO_IDS: ReadonlySet<string> = new Set();

export default function LibraryContent({
  categories,
  items,
  open,
  notes = NO_NOTES,
  outside = NO_IDS,
  profileOnly = NO_IDS,
  onOpen,
  onInsert,
  onInsertBlock,
  disabled,
  blockTargetName,
  searching = false,
}: {
  /** Kategorie, které po hledání a filtru ještě něco mají, v pořadí zobrazení. */
  categories: CatalogCategoryInfo[];
  /** Už vyhledané a zúžené prvky; dílek je jen rozdělí podle kategorie. */
  items: CatalogItem[];
  /** Id prvku s otevřeným náhledem. */
  open: string | null;
  /** „kvůli profilu: …“ nebo „mimo profil“ podle id prvku. */
  notes?: Readonly<Record<string, string>>;
  outside?: ReadonlySet<string>;
  /** Kategorie ve výběru jen kvůli profilu projektu. */
  profileOnly?: ReadonlySet<string>;
  onOpen: (id: string) => void;
  onInsert: (id: string) => void;
  onInsertBlock: (id: string) => void;
  disabled: boolean;
  blockTargetName: string | null;
  searching?: boolean;
}) {
  if (!categories.length) return <p className="library-navbar__empty">Katalog nic takového nemá. Zkuste jiné slovo.</p>;
  return (
    <div className="library-navbar__shelves">
      {CATALOG_FAMILIES.map((family) => {
        const groups = categories.filter((category) => family.categories.includes(category.id));
        if (!groups.length) return null;
        return <details key={family.id + (searching ? "-search" : "")} className="library-navbar__family" open={searching} data-testid={"library-family-" + family.id}>
          <summary>{family.label}</summary>
          {groups.map((category) => {
        const own = items.filter((item) => item.category === category.id);
        return (
          <section
            key={category.id}
            className={"library-navbar__shelf library-navbar__shelf--" + category.id}
            aria-label={category.label}
            data-testid={"library-category-" + category.id}
          >
            <h3 className="library-navbar__shelf-head" title={category.hint}>
              <span className="library-navbar__icon">
                <Icon name={categoryIcon(category.id)} size={16} />
              </span>
              <span className="library-navbar__shelf-label">{category.label}</span>
              {profileOnly.has(category.id) && <span className="library-navbar__fit">kvůli profilu</span>}
              <small className="library-navbar__shelf-count">{own.length}</small>
            </h3>
            <ul className="library-navbar__items">
              {own.map((item) => {
                const isOpen = open === item.id;
                return (
                  <li
                    key={item.id}
                    className={
                      "library-navbar__item" +
                      (isOpen ? " library-navbar__item--open" : "") +
                      (outside.has(item.id) ? " library-navbar__item--outside" : "")
                    }
                    draggable={!disabled}
                    title="Táhněte na plátno (nová komponenta), na kartu (potomek) nebo do oblasti."
                    data-testid={"library-item-" + item.id}
                    onDragStart={(event: DragEvent<HTMLLIElement>) => startCatalogDrag(event.dataTransfer, item.id)}
                  >
                    <button
                      type="button"
                      className="library-navbar__item-toggle"
                      aria-expanded={isOpen}
                      onClick={() => onOpen(item.id)}
                    >
                      <span className="library-navbar__item-text">
                        <span className="library-navbar__item-label">{item.label}</span>
                        <span className="library-navbar__item-purpose">{item.purpose}</span>
                        {notes[item.id] && <span className="library-navbar__fit">{notes[item.id]}</span>}
                      </span>
                      <Icon className="library-navbar__item-grip" name="grip-vertical" size={16} />
                    </button>
                    <button type="button" className="library-navbar__insert" disabled={disabled} data-testid={"library-insert-" + item.id}
                      title="Vložit novou komponentu do aktuálně otevřené vrstvy" onClick={() => onInsert(item.id)}>Vložit</button>
                    {isOpen && <><LibraryItemDetail item={item} />
                      <button type="button" className="library-navbar__insert-block" disabled={disabled || !blockTargetName}
                        data-testid={"library-block-" + item.id} onClick={() => onInsertBlock(item.id)}>
                        {blockTargetName ? `Přidat jako blok do karty „${blockTargetName}“` : "Pro vložení bloku vyberte kartu"}
                      </button>
                    </>}
                  </li>
                );
              })}
            </ul>
          </section>
        );
          })}
        </details>;
      })}
    </div>
  );
}
