// Vazba stavu sekcí Agenti a Postupy na React. Hook nemá vlastní logiku: drží jednu hodnotu, mění
// ji funkcemi z agent-navbar.ts a po každé změně ji uloží pod jediný klíč aplikace. Otevření
// a zavření sekce ani zkratka Ctrl+Shift+. sem nepatří — drží je `layout/panel-dock/`. Volá ho
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
  type AgentSection,
} from "./agent-navbar";
import type { AgentCategory } from "@/editor/component-library/agent-catalog/logic/agent-catalog";

export type AgentNavbarApi = {
  state: AgentNavbarState;
  category: (section: AgentSection, category: AgentCategory) => void;
  search: (section: AgentSection, query: string) => void;
  tab: (tab: AgentNavbarTab) => void;
};

export function useAgentNavbar(): AgentNavbarApi {
  const [state, setState] = useState<AgentNavbarState>(readState);
  useEffect(() => { writeState(state); }, [state]);
  return {
    state,
    category: (section, value) => setState((current) => setCategory(current, section, value)),
    search: (section, value) => setState((current) => setQuery(current, section, value)),
    tab: (value) => setState((current) => setTab(current, value)),
  };
}
