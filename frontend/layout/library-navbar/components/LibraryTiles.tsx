// Dílek Elementy: mřížka dlaždic ve dvou sloupcích. Dlaždice ukáže ikonu, popisek a tichou řádku
// rozpadu (kolik dílků a pravidel položka nese) a je zdrojem tažení na plátno. Klik ji nechá ukázat
// celý rozpad v její kategorii, aby se ke stejnému obsahu dalo dojít i klávesnicí. Prvek přivedený
// profilem projektu nese třetí značku s důvodem, prvek mimo profil je ztlumený — obojí dostane hotové.
import type { DragEvent } from "react";
import { categoryIcon, startCatalogDrag } from "@/layout/library-navbar/logic/library-navbar";
import Icon from "@/ui-kit/icon/components/Icon";
import {
  decompositionSummary,
  type CatalogCategory,
  type CatalogItem,
} from "@/editor/component-library/library-catalog/logic/library-catalog";

const NO_NOTES: Readonly<Record<string, string>> = {};
const NO_OUTSIDE: ReadonlySet<string> = new Set();

export default function LibraryTiles({
  items,
  notes = NO_NOTES,
  outside = NO_OUTSIDE,
  onOpenCategory,
}: {
  items: CatalogItem[];
  /** „kvůli profilu: …“ nebo „mimo profil“ podle id prvku. */
  notes?: Readonly<Record<string, string>>;
  outside?: ReadonlySet<string>;
  onOpenCategory: (category: CatalogCategory) => void;
}) {
  if (!items.length) return <p className="library-navbar__empty">Katalog nic takového nemá. Zkuste jiné slovo.</p>;
  return (
    <div className="library-navbar__grid">
      {items.map((item) => {
        // Rozpad je jedna věta („3 dílky · 5 pravidel“); dlaždice ji chce jako dvě značky,
        // proto se tu jen rozdělí na půlce — počítá se to jednou, v decompositionSummary.
        const [partsBadge, rulesBadge] = decompositionSummary(item).split(" · ");
        return (
          <button
            key={item.id}
            type="button"
            className={
              "library-navbar__tile library-navbar__tile--" + item.category +
              (outside.has(item.id) ? " library-navbar__tile--outside" : "")
            }
            draggable
            title={item.hint + " — klik ukáže rozpad v kategorii"}
            data-testid={"library-tile-" + item.id}
            onDragStart={(event: DragEvent<HTMLButtonElement>) => startCatalogDrag(event.dataTransfer, item.id)}
            onClick={() => onOpenCategory(item.category)}
          >
            <span className="library-navbar__icon">
              <Icon name={categoryIcon(item.category)} size={16} />
            </span>
            <Icon className="library-navbar__tile-grip" name="grip-vertical" size={16} />
            <span className="library-navbar__tile-label">{item.label}</span>
            <span className="library-navbar__tile-desc">{item.hint}</span>
            <span className="library-navbar__tile-badges">
              <span className="library-navbar__tile-badge library-navbar__tile-badge--accent">{partsBadge}</span>
              <span className="library-navbar__tile-badge">{rulesBadge}</span>
              {notes[item.id] && <span className="library-navbar__tile-badge library-navbar__tile-badge--fit">{notes[item.id]}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}
