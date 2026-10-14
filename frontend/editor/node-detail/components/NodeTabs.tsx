// Záložky detailu uzlu: jediná řada tlačítek s ARIA tablistem a pohybem šipkami. Dílek nic neví o obsahu
// záložek ani o ukládání; vybranou záložku drží rodič (NodePanel) a změna bublá nahoru přes onTab.
import type { KeyboardEvent, ReactNode } from "react";

export type NodeTab = "spec" | "links" | "work" | "ideas" | "rounds";
export const TABS: { key: NodeTab; label: string }[] = [
  { key: "spec", label: "Zadání" },
  { key: "links", label: "Vazby" },
  { key: "work", label: "Práce" },
  { key: "ideas", label: "Podněty" },
  { key: "rounds", label: "Historie kol" },
];

export default function NodeTabs({ tab, onTab, badges }: {
  tab: NodeTab;
  onTab: (tab: NodeTab) => void;
  /** Drobný odznak za názvem záložky (např. počet otevřených podnětů); obsah dodá rodič. */
  badges?: Partial<Record<NodeTab, ReactNode>>;
}) {
  function navigate(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number;
    switch (event.key) {
      case "ArrowRight": next = (index + 1) % TABS.length; break;
      case "ArrowLeft": next = (index + TABS.length - 1) % TABS.length; break;
      case "Home": next = 0; break;
      case "End": next = TABS.length - 1; break;
      default: return;
    }
    event.preventDefault();
    onTab(TABS[next].key);
    // Fokus zůstává v tomto tablistu, ne v jiném inspektoru či skrytém panelu.
    event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  }
  return (
    <div className="panel-tabs" role="tablist" aria-label="Části uzlu">
      {TABS.map((item, index) => (
        <button
          key={item.key}
          type="button"
          role="tab"
          id={"node-tab-" + item.key}
          aria-selected={tab === item.key}
          aria-controls={"node-panel-" + item.key}
          tabIndex={tab === item.key ? 0 : -1}
          onKeyDown={(event) => navigate(event, index)}
          onClick={() => onTab(item.key)}
        >
          {item.label}
          {badges?.[item.key]}
        </button>
      ))}
    </div>
  );
}
