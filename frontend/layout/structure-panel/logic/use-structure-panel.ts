// Vazba stavu Struktury na React. Hook nemá vlastní logiku: drží jednu hodnotu, mění ji funkcemi
// ze structure-panel.ts a po každé změně ji uloží pod jediný klíč aplikace. Otevření panelu ani
// zkratka sem nepatří — drží je `layout/panel-dock/`. Volá ho rodič (App) jednou.
import { useEffect, useState } from "react";
import { readStructure, setFilter, setQuery, setTab, toggleGroup, writeStructure, type StructureState, type StructureTab } from "./structure-panel";
import type { LayerFilter, LayerGroupId } from "./layer-list";

export type StructurePanelApi = {
  state: StructureState;
  tab: (tab: StructureTab) => void;
  filter: (filter: LayerFilter) => void;
  search: (query: string) => void;
  group: (group: LayerGroupId) => void;
};

export function useStructurePanel(): StructurePanelApi {
  const [state, setState] = useState<StructureState>(readStructure);
  useEffect(() => { writeStructure(state); }, [state]);
  return {
    state,
    tab: (value) => setState((current) => setTab(current, value)),
    filter: (value) => setState((current) => setFilter(current, value)),
    search: (value) => setState((current) => setQuery(current, value)),
    group: (value) => setState((current) => toggleGroup(current, value)),
  };
}
