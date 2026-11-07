import { useId, useState, type KeyboardEvent } from "react";
import type { BoardLayout, LaidBall } from "../logic/linie-board";
import { labelOffsets, type Labels } from "../logic/linie-labels";
import type { LayerState } from "../logic/linie-prefs";
import { xOf } from "../logic/linie-zoom";
import LinieBall from "./LinieBall";
import LinieLink from "./LinieLink";

type Props = {
  layout: BoardLayout; selected: string; labels: Labels; lit: Set<string> | null; layers: LayerState;
  onPick: (ticketId: string) => void;
};

const TIP_W = 260;

/**
 * Plátno Linie: čáry řádků, spojnice, skutečné merge, kuličky na svém čase a jejich popisky v patrech z `labels`.
 * Vybraná kulička má stálý prstenec; ztlumené (mimo zvolenou frontu) jen zprůhlední. Plány ostatních kuliček a commity
 * jsou vrstvy, vybrané se ukážou vždy. Prázdné místo nese `data-pan`: tažením se posouvá.
 */
export default function LiniePlot({ layout, selected, labels, lit, layers, onPick }: Props) {
  const gradientId = `linie-g${useId().replace(/[^\w-]/g, "")}`; // dvojtečky z useId by v url(#…) neprošly
  const [tip, setTip] = useState<LaidBall | null>(null);
  const mine = (ticketId: string) => ticketId === selected;
  const links = layout.links.filter((link) => link.kind === "merged" || layers.plans || mine(link.ticketId));
  const commits = layout.commits.filter((commit) => layers.commits || mine(commit.ticketId));
  const nowX = layout.now === null ? null : xOf({ t0: layout.t0, k: layout.k }, layout.now);
  const key = (ball: LaidBall) => (event: KeyboardEvent) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPick(ball.ticketId); } };

  return (
    <div className="pletor-dashboard__linie-plot" data-pan style={{ width: layout.width, height: layout.height }}>
      <svg className="pletor-dashboard__linie-svg" width={layout.width} height={layout.height} role="img" aria-label="Řádky a kuličky Linie">
        {layout.rows.map((row) => (
          <line key={row.id} x1={0} y1={row.y} x2={layout.width} y2={row.y} stroke={row.color}
            strokeWidth={row.fixed ? 3 : 2} opacity={row.collapsed ? 0.25 : row.fixed ? 0.9 : 0.55} />
        ))}
        {nowX !== null && <line className="pletor-dashboard__linie-now" x1={nowX} y1={0} x2={nowX} y2={layout.height} />}
        {links.map((link, index) => <LinieLink key={index} link={link} id={`${gradientId}-${index}`} />)}
        {layout.merges.map((merge) => (
          <circle key={merge.sha7} cx={merge.x} cy={merge.y} r={5} fill={merge.color}><title>{`${merge.sha7}: ${merge.title}`}</title></circle>
        ))}
        {commits.map((commit) => (
          <rect key={`${commit.ticketId}-${commit.ref}`} className="pletor-dashboard__linie-cube" x={commit.x - 4} y={commit.y - 4} width={8} height={8}>
            <title>{`${commit.ref} · ${commit.at}`}</title>
          </rect>
        ))}
        {layout.balls.map((ball) => {
          const slot = labels.slots[ball.ticketId];
          const off = slot && labelOffsets(slot);
          return (
            <g key={ball.ticketId} role="button" tabIndex={0} aria-label={`${ball.title}, ${ball.stateLabel}`} aria-pressed={mine(ball.ticketId)}
              className={`pletor-dashboard__linie-pick${lit && !lit.has(ball.ticketId) ? " pletor-dashboard__linie-pick--dim" : ""}`}
              onClick={() => onPick(ball.ticketId)} onKeyDown={key(ball)}
              onMouseEnter={() => setTip(ball)} onMouseLeave={() => setTip(null)} onFocus={() => setTip(ball)} onBlur={() => setTip(null)}>
              {mine(ball.ticketId) && <circle className="pletor-dashboard__linie-ring" cx={ball.x} cy={ball.y} r={16} />}
              <LinieBall fill={ball.fill} color={ball.color} toColor={ball.toColor !== ball.color ? ball.toColor : undefined} x={ball.x} y={ball.y} />
              {off && <text x={ball.x} y={ball.y + off.name} className="pletor-dashboard__linie-ball-name">{ball.label}</text>}
              {off && off.state !== null && <text x={ball.x} y={ball.y + off.state} className="pletor-dashboard__linie-ball-state">{ball.stateLabel}</text>}
            </g>
          );
        })}
        {labels.clusters.map((cluster) => {
          const first = layout.balls.find((ball) => ball.ticketId === cluster.ids[0]);
          return first && (
            <g key={`${cluster.rowId}-${cluster.x}`} role="button" tabIndex={0} className="pletor-dashboard__linie-pick" aria-label={`Další ${cluster.ids.length} kuličky, výčet v detailu`}
              onClick={() => onPick(cluster.ids[0])} onKeyDown={key(first)}>
              <text x={cluster.x + 12} y={first.y - 12} className="pletor-dashboard__linie-cluster">+{cluster.ids.length}</text>
            </g>
          );
        })}
      </svg>
      {tip && (
        <div className="pletor-dashboard__linie-tip" style={{ left: Math.min(tip.x + 16, layout.width - TIP_W), top: Math.max(tip.y - 70, 4) }}>
          <strong className="pletor-dashboard__linie-tip-title">{tip.hover.title}</strong>
          {tip.hover.mark && <span><span className="pletor-dashboard__linie-tip-key">značka</span>{tip.hover.mark}</span>}
          <span><span className="pletor-dashboard__linie-tip-key">stav</span>{tip.stateLabel}</span>
          <span><span className="pletor-dashboard__linie-tip-key">vznik</span>{tip.hover.created}</span>
          <span><span className="pletor-dashboard__linie-tip-key">začlenění</span>{tip.hover.merged}</span>
          <span><span className="pletor-dashboard__linie-tip-key">commity|PR|merge</span>{tip.hover.counts}</span>
          <span><span className="pletor-dashboard__linie-tip-key">větev</span>{tip.hover.branch}</span>
          <span className="pletor-dashboard__linie-tip-hint">klik = detail</span>
        </div>
      )}
    </div>
  );
}
