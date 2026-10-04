// Vazba stavu Knihovny na React. Hook nemá vlastní logiku: drží jednu hodnotu, mění ji funkcemi
// z library-navbar.ts a po každé změně ji uloží pod jediný klíč aplikace. Otevření a zavření panelu
// ani zkratka Ctrl+Shift+, sem nepatří — drží je `layout/panel-dock/`. Volá ho rodič (App) jednou
// a rozdává výsledek dílkům v props.
import { useEffect, useState } from "react";
import {
  openItem,
  readLibraryNavbar,
  setPageFilter,
  setPageQuery,
  setQuery,
  setTab,
  toggleGroup,
  writeLibraryNavbar,
  type LibraryNavbarState,
  type LibraryTab,
} from "./library-navbar";
import type { LayerFilter, LayerGroupId } from "./layer-list";

export type LibraryNavbarApi = {
  state: LibraryNavbarState;
  tab: (tab: LibraryTab) => void;
  search: (query: string) => void;
  /** Otevře nebo zavře náhled prvku. */
  item: (id: string) => void;
  /** STRÁNKA: filtr skupin, vlastní hledání a sbalení skupiny — tentýž klíč, jiná pole. */
  pageFilter: (filter: LayerFilter) => void;
  pageSearch: (query: string) => void;
  group: (group: LayerGroupId) => void;
};

export function useLibraryNavbar(initialTab?: LibraryTab): LibraryNavbarApi {
  const [state, setState] = useState<LibraryNavbarState>(() => {
    const stored = readLibraryNavbar();
    return initialTab ? { ...stored, tab: initialTab } : stored;
  });
  useEffect(() => { writeLibraryNavbar(state); }, [state]);
  return {
    state,
    tab: (value) => setState((current) => setTab(current, value)),
    search: (value) => setState((current) => setQuery(current, value)),
    item: (value) => setState((current) => openItem(current, value)),
    pageFilter: (value) => setState((current) => setPageFilter(current, value)),
    pageSearch: (value) => setState((current) => setPageQuery(current, value)),
    group: (value) => setState((current) => toggleGroup(current, value)),
  };
}
