// Dvě záložky Já / Agenti: postava a robot v barvě aktéra, počet načtených a kolik z nich selhalo.
import Icon from "@/ui-kit/icon/components/Icon";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";
import type { Actor, TabStats } from "@/editor/canvas/activity-log/logic/activity-log";

const TABS: { actor: Actor; label: string; icon: IconName }[] = [
  { actor: "human", label: "Já", icon: "user" },
  { actor: "agent", label: "Agenti", icon: "bot" },
];

export default function ActivityLogTabs({ tab, stats, onTab }: {
  tab: Actor;
  stats: Record<Actor, TabStats>;
  onTab: (actor: Actor) => void;
}) {
  return (
    <div className="activity-log__tabs" role="tablist" aria-label="Kdo zapisoval">
      {TABS.map((item) => {
        const active = item.actor === tab;
        const { count, failed } = stats[item.actor];
        return (
          <button key={item.actor} type="button" role="tab" aria-selected={active}
            className={`activity-log__tab activity-log__tab--${item.actor}` + (active ? " activity-log__tab--active" : "")}
            onClick={() => onTab(item.actor)} data-testid={`activity-log-tab-${item.actor}`}>
            <Icon name={item.icon} size={16} />
            {item.label}
            <span className="activity-log__count">{count}</span>
            {failed > 0 && <span className="activity-log__count activity-log__count--failed" title={`Selhalo: ${failed}`}><Icon name="x" size={16} />{failed}</span>}
          </button>
        );
      })}
    </div>
  );
}
