// Panel Záznam činnosti pod lištou u pravého okraje. Skládá záložky, filtr karty a seznam po dnech;
// sám nic nenačítá. Escape i × hlásí zavření nahoru.
import { useEffect } from "react";
import ActivityLogTabs from "@/editor/canvas/activity-log/components/ActivityLogTabs";
import ActivityLogList from "@/editor/canvas/activity-log/components/ActivityLogList";
import type { ActivityLogState } from "@/editor/canvas/activity-log/logic/use-activity-log";
import { tabStats, type Actor } from "@/editor/canvas/activity-log/logic/activity-log";
import Icon from "@/ui-kit/icon/components/Icon";

export default function ActivityLogPanel({ tab, log, nodes, selectedName, onlySelected, onTab, onToggleSelected, onLoadOlder, onOpenNode, onClose }: {
  tab: Actor;
  log: ActivityLogState;
  nodes: { id: string; name: string }[];
  /** Jméno vybrané karty; bez výběru se filtr nenabízí. */
  selectedName: string | null;
  onlySelected: boolean;
  onTab: (actor: Actor) => void;
  onToggleSelected: () => void;
  onLoadOlder: () => void;
  onOpenNode: (id: string) => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [onClose]);
  const current = log[tab];
  return (
    <section className="activity-log__panel" role="dialog" aria-label="Záznam činnosti" data-testid="activity-log-panel">
      <header className="activity-log__head">
        <h2 className="activity-log__title">Záznam činnosti</h2>
        <button type="button" className="activity-log__close" aria-label="Zavřít záznam činnosti" onClick={onClose}>
          <Icon name="x" size={16} />
        </button>
      </header>
      <ActivityLogTabs tab={tab} stats={{ human: tabStats(log.human), agent: tabStats(log.agent) }} onTab={onTab} />
      {(selectedName || onlySelected) && (
        <button type="button" className={"activity-log__filter" + (onlySelected ? " activity-log__filter--active" : "")}
          aria-pressed={onlySelected} onClick={onToggleSelected} title="Ukázat jen zápisy, které se týkají vybrané karty">
          <Icon name="filter" size={16} />
          <span className="activity-log__filter-text">Jen vybraná karta{selectedName ? `: ${selectedName}` : ""}</span>
        </button>
      )}
      {current.error && <p className="activity-log__error" role="alert">{current.error}</p>}
      <ActivityLogList actor={tab} log={current} nodes={nodes} onLoadOlder={onLoadOlder} onOpenNode={onOpenNode} />
    </section>
  );
}
