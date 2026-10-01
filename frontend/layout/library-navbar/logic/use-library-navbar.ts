// Vazba stavu Knihovny na React. Hook nemá vlastní logiku: drží jednu hodnotu, mění ji funkcemi
// z library-navbar.ts a po každé změně ji uloží pod jediný klíč aplikace. Otevření a zavření panelu
// ani zkratka Ctrl+Shift+, sem nepatří — drží je `layout/panel-dock/`. Volá ho rodič (App) jednou
// a rozdává výsledek dílkům v props.
import { useEffect, useState } from "react";
import {
  openCategory,
  readLibraryNavbar,
  setMode,
  setPageFilter,
  setPageQuery,
  setQuery,
  setTab,
  toggleGroup,
  writeLibraryNavbar,
  type LibraryMode,
  type LibraryNavbarState,
  type LibraryTab,
} from "./library-navbar";
import type { LayerFilter, LayerGroupId } from "./layer-list";
import type { CatalogCategory } from "@/editor/component-library/library-catalog/logic/library-catalog";

export type LibraryNavbarApi = {
  state: LibraryNavbarState;
  tab: (tab: LibraryTab) => void;
  mode: (mode: LibraryMode) => void;
  search: (query: string) => void;
  category: (category: CatalogCategory) => void;
  /** STRÁNKA: filtr skupin, vlastní hledání a sbalení skupiny — tentýž klíč, jiná pole. */
  pageFilter: (filter: LayerFilter) => void;
  pageSearch: (query: string) => void;
  group: (group: LayerGroupId) => void;
};

export function useLibraryNavbar(): LibraryNavbarApi {
  const [state, setState] = useState<LibraryNavbarState>(readLibraryNavbar);
  useEffect(() => { writeLibraryNavbar(state); }, [state]);
  return {
    state,
    tab: (value) => setState((current) => setTab(current, value)),
    mode: (value) => setState((current) => setMode(current, value)),
    search: (value) => setState((current) => setQuery(current, value)),
    category: (value) => setState((current) => openCategory(current, value)),
    pageFilter: (value) => setState((current) => setPageFilter(current, value)),
    pageSearch: (value) => setState((current) => setPageQuery(current, value)),
    group: (value) => setState((current) => toggleGroup(current, value)),
  };
}
