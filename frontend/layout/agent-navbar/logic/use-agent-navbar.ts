// Vazba stavu panelu Agenti a postupy na React. Hook nemá vlastní logiku: drží jednu hodnotu, mění
// ji funkcemi z agent-navbar.ts a po každé změně ji uloží pod jediný klíč aplikace. Otevření
// a zavření panelu ani zkratka Ctrl+Shift+. sem nepatří — drží je `layout/panel-dock/`. Volá ho
// rodič (App) jednou a výsledek rozdá dílkům v props.
import { useEffect, useState } from "react";
import {
  readState,
  setCategory,
  setQuery,
  setTab,
  writeState,
  type AgentNavbarState,
  type AgentNavbarTab,
} from "./agent-navbar";
import type { AgentCategory } from "@/editor/component-library/agent-catalog/logic/agent-catalog";

export type AgentNavbarApi = {
  state: AgentNavbarState;
  category: (category: AgentCategory) => void;
  search: (query: string) => void;
  tab: (tab: AgentNavbarTab) => void;
};

export function useAgentNavbar(): AgentNavbarApi {
  const [state, setState] = useState<AgentNavbarState>(readState);
  useEffect(() => { writeState(state); }, [state]);
  return {
    state,
    category: (value) => setState((current) => setCategory(current, value)),
    search: (value) => setState((current) => setQuery(current, value)),
    tab: (value) => setState((current) => setTab(current, value)),
  };
}
