import type { KeyboardEvent, ReactNode } from "react";
import { CARD_TABS, type CardTab } from "../logic/card-drawer-store";

export const TAB_LABEL: Record<CardTab, string> = { spec: "Zadání", steps: "Kroky", lens: "Lens", run: "Běh", review: "Review & PR", history: "Historie" };

/** Šest záložek detailu (ARIA tablist, šipky); každá nese malý stavový údaj (verze, postup, hlava Lens, odpočet, brána). */
export default function DrawerTabs({ tab, badges, available, onTab }: {
  tab: CardTab; badges: Partial<Record<CardTab, ReactNode>>; available: CardTab[]; onTab: (tab: CardTab) => void;
}) {
  const tabs = CARD_TABS.filter(item => available.includes(item));
  function navigate(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length
      : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    onTab(tabs[next]);
    event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  }
  return <div className="card-drawer__tabs" role="tablist" aria-label="Části karty">
    {tabs.map((item, index) => <button key={item} type="button" role="tab" id={`card-drawer-tab-${item}`} aria-selected={tab === item}
      aria-controls={`card-drawer-panel-${item}`} tabIndex={tab === item ? 0 : -1} className="card-drawer__tab" data-oh-tab={item}
      onKeyDown={event => navigate(event, index)} onClick={() => onTab(item)}>
      {TAB_LABEL[item]}{badges[item] && <span className="card-drawer__tab-badge">{badges[item]}</span>}
    </button>)}
  </div>;
}
