// Co Knihovna ukáže pro profil projektu: katalog se rozdělí stejnou funkcí jako u Agentů
// (`catalogView` ze šuplíku), kategorie, které jsou ve výběru jen kvůli profilu, dostanou štítek
// a stojí nahoře, a každý prvek nese poznámku („kvůli profilu: …“ nebo „mimo profil“).
// Bez Reactu; komponenty jen vypíšou výsledek. Test vedle v library-scope.test.ts.
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { catalogView, fitNote, profileOnlyGroup, type CatalogScopeOptions, type CatalogView } from "@/layout/panel-dock/logic/panel-drawer";
import {
  CATALOG_CATEGORIES,
  searchItems,
  type CatalogCategory,
  type CatalogCategoryInfo,
  type CatalogItem,
} from "@/editor/component-library/library-catalog/logic/library-catalog";

export type LibraryView = CatalogView<CatalogItem> & {
  /** Kategorie, které ve výběru něco mají; ty „kvůli profilu“ jsou první. */
  categories: CatalogCategoryInfo[];
  profileOnly: ReadonlySet<CatalogCategory>;
  /** Poznámka k prvku podle id; univerzální prvek poznámku nemá. */
  notes: Readonly<Record<string, string>>;
  outsideIds: ReadonlySet<string>;
};

export function libraryView(items: CatalogItem[], profile: ProjectProfile, options: CatalogScopeOptions): LibraryView {
  const view = catalogView(items, profile, options, searchItems);
  const outside = new Set<CatalogItem>(view.outside);
  const notes: Record<string, string> = {};
  for (const item of view.shown) {
    const note = fitNote(item, profile, outside);
    if (note) notes[item.id] = note;
  }
  const inCategory = (id: CatalogCategory) => view.shown.filter((item) => item.category === id);
  const present = CATALOG_CATEGORIES.filter((category) => inCategory(category.id).length > 0);
  const profileOnly = new Set(present.filter((category) => profileOnlyGroup(inCategory(category.id), profile)).map((category) => category.id));
  const categories = [...present.filter((c) => profileOnly.has(c.id)), ...present.filter((c) => !profileOnly.has(c.id))];
  return { ...view, categories, profileOnly, notes, outsideIds: new Set(view.outside.map((item) => item.id)) };
}
