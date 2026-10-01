// Co Agenti a postupy ukážou pro profil projektu: vybraná kategorie se rozdělí stejnou funkcí jako
// Knihovna (`catalogView` ze šuplíku), čísla u kategorií počítají jen to, co filtr ukazuje, a každý
// postup nese poznámku („kvůli profilu: …“ nebo „mimo profil“). Bez Reactu; test vedle.
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { catalogView, fitNote, type CatalogScopeOptions, type CatalogView } from "@/layout/panel-dock/logic/panel-drawer";
import { splitByProfile } from "@/editor/component-library/library-catalog/logic/catalog-fit";
import {
  AGENT_CATEGORIES,
  AGENT_ITEMS,
  agentItemsOf,
  searchAgentItems,
  type AgentCategory,
  type AgentItem,
} from "@/editor/component-library/agent-catalog/logic/agent-catalog";

export type AgentView = CatalogView<AgentItem> & {
  /** Číslo u řádku kategorie: s filtrem projektu jen to, co k projektu sedí. */
  counts: Record<AgentCategory, number>;
  notes: Readonly<Record<string, string>>;
  outsideIds: ReadonlySet<string>;
};

export function agentView(
  category: AgentCategory,
  profile: ProjectProfile,
  options: CatalogScopeOptions,
  items: AgentItem[] = AGENT_ITEMS,
): AgentView {
  const view = catalogView(agentItemsOf(category, items), profile, options, searchAgentItems);
  const narrowed = view.filtering && options.scope === "fitting";
  const counts = Object.fromEntries(
    AGENT_CATEGORIES.map((info) => {
      const all = agentItemsOf(info.id, items);
      return [info.id, narrowed ? splitByProfile(all, profile).fitting.length : all.length];
    }),
  ) as Record<AgentCategory, number>;
  const outside = new Set<AgentItem>(view.outside);
  const notes: Record<string, string> = {};
  for (const item of view.shown) {
    const note = fitNote(item, profile, outside);
    if (note) notes[item.id] = note;
  }
  return { ...view, counts, notes, outsideIds: new Set(view.outside.map((item) => item.id)) };
}
