// Dílek Bloky: kategorie pod sebou, každá se šipkou a počtem položek; kategorie, která je ve výběru
// jen kvůli profilu projektu, nese štítek „kvůli profilu“ (pořadí i štítek dostane hotové). Rozbalená kategorie
// otevře vedle panelu sloupec náhledů — a náhled není obrázek, je to začátek rozpadu položky.
// Náhled se dá chytit a táhnout na plátno stejně jako dlaždice.
//
// Všechny značky jsou kreslené ikony ze sady `ui-kit/icon`, ne Unicode glyfy — i u náhledu, kde
// nese položka ikonu **své kategorie** (`categoryIcon`), ne vlastní znak z katalogu: sloupec se pak
// čte jedním pohledem a katalog (`library-catalog.ts`) zůstává beze změny. Stejné pravidlo platí
// v polici postupů (`AgentNavbarCatalog`).
import type { DragEvent } from "react";
import { categoryIcon, startCatalogDrag } from "@/layout/library-navbar/logic/library-navbar";
import Icon from "@/ui-kit/icon/components/Icon";
import {
  decompositionSummary,
  type CatalogCategory,
  type CatalogCategoryInfo,
  type CatalogItem,
} from "@/editor/component-library/library-catalog/logic/library-catalog";

const PREVIEW_STEPS = 3;

const NO_NOTES: Readonly<Record<string, string>> = {};
const NO_IDS: ReadonlySet<string> = new Set();

export default function LibraryCategories({
  categories,
  items,
  notes = NO_NOTES,
  outside = NO_IDS,
  profileOnly = NO_IDS,
  open,
  onOpen,
}: {
  /** Kategorie, které po hledání ještě mají co nabídnout. */
  categories: CatalogCategoryInfo[];
  /** Už vyhledané položky; dílek je jen rozdělí podle kategorie. */
  items: CatalogItem[];
  /** „kvůli profilu: …“ nebo „mimo profil“ podle id prvku. */
  notes?: Readonly<Record<string, string>>;
  outside?: ReadonlySet<string>;
  /** Kategorie ve výběru jen kvůli profilu projektu. */
  profileOnly?: ReadonlySet<string>;
  open: CatalogCategory | null;
  onOpen: (category: CatalogCategory) => void;
}) {
  if (!categories.length) return <p className="library-navbar__empty">Katalog nic takového nemá. Zkuste jiné slovo.</p>;
  const openInfo = categories.find((category) => category.id === open) ?? null;
  const previews = openInfo ? items.filter((item) => item.category === openInfo.id) : [];
  return (
    <div className="library-navbar__categories">
      {categories.map((category) => {
        const count = items.filter((item) => item.category === category.id).length;
        const isOpen = openInfo?.id === category.id;
        return (
          <button
            key={category.id}
            type="button"
            className={
              "library-navbar__category library-navbar__category--" + category.id +
              (isOpen ? " library-navbar__category--open" : "")
            }
            aria-expanded={isOpen}
            title={category.hint}
            data-testid={"library-category-" + category.id}
            onClick={() => onOpen(category.id)}
          >
            <span className="library-navbar__icon">
              <Icon name={categoryIcon(category.id)} size={16} />
            </span>
            <span className="library-navbar__category-label">{category.label}</span>
            {profileOnly.has(category.id) && <span className="library-navbar__fit">kvůli profilu</span>}
            <small className="library-navbar__category-count">{count}</small>
            <Icon
              className="library-navbar__category-chevron"
              name={isOpen ? "chevron-left" : "chevron-right"}
              size={16}
            />
          </button>
        );
      })}
      {openInfo && (
        <aside className="library-navbar__previews" aria-label={"Náhledy kategorie " + openInfo.label}>
          <h4 className="library-navbar__previews-title">{openInfo.label}</h4>
          <p className="library-navbar__previews-hint">{openInfo.hint}</p>
          {previews.map((item) => (
            <article
              key={item.id}
              className={"library-navbar__preview" + (outside.has(item.id) ? " library-navbar__preview--outside" : "")}
              draggable
              data-testid={"library-preview-" + item.id}
              onDragStart={(event: DragEvent<HTMLElement>) => startCatalogDrag(event.dataTransfer, item.id)}
            >
              <span className="library-navbar__preview-title">
                <Icon className="library-navbar__preview-icon" name={categoryIcon(item.category)} size={16} />
                {item.label}
              </span>
              <span className="library-navbar__preview-hint">{item.hint}</span>
              {notes[item.id] && <span className="library-navbar__fit">{notes[item.id]}</span>}
              {item.decomposition.slice(0, PREVIEW_STEPS).map((step) => (
                <span key={step.title} className="library-navbar__preview-step">
                  <b className="library-navbar__preview-step-title">{step.title}</b> {step.text}
                </span>
              ))}
              <small className="library-navbar__preview-summary">{decompositionSummary(item)}</small>
            </article>
          ))}
        </aside>
      )}
    </div>
  );
}
