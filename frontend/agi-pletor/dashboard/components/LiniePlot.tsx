import "../styles/pletor-dashboard-linie-plot.css";
import { useId, useState, type KeyboardEvent } from "react";
import type { BoardLayout, LaidBall } from "../logic/linie-board";
import { labelAnchor, labelOffsets } from "../logic/linie-labels";
import type { LayerState } from "../logic/linie-prefs";
import { ballTip, type Tip } from "../logic/linie-tip";
import { xOf } from "../logic/linie-zoom";
import LinieBall from "./LinieBall";
import LinieLink from "./LinieLink";
import { PlotMarksHtml, PlotMarksSvg } from "./LiniePlotMarks";
import LinieTip from "./LinieTip";

type Props = {
  layout: BoardLayout; selected: string; lit: Set<string> | null; layers: LayerState;
  onPick: (ticketId: string) => void; onPickCommit: (ticketId: string, sha: string) => void;
};

/**
 * Plátno Linie: osy řádků (pevné 3 px, ostatní 2 px), spojnice, skutečné merge, kuličky na svém čase a jejich popisky
 * v patrech z `layout.labels`; značky (commity, worktree, tagy, nasazení, pilulky PR) kreslí `LiniePlotMarks`. Vybraná
 * kulička má stálý prstenec; ztlumené (mimo zvolenou frontu) jen zprůhlední. Plány ostatních kuliček mimo vrstvu jsou
 * slabé (.25) bez popisku. Kulička i kostka commitu sdílejí jednu bublinu `LinieTip`. Prázdné místo nese `data-pan`.
 */
export default function LiniePlot({ layout, selected, lit, layers, onPick, onPickCommit }: Props) {
  const gradientId = `linie-g${useId().replace(/[^\w-]/g, "")}`; // dvojtečky z useId by v url(#…) neprošly
  const [tip, setTip] = useState<Tip | null>(null);
  const mine = (ticketId: string) => ticketId === selected;
  const nowX = layout.now === null ? null : xOf({ t0: layout.t0, k: layout.k }, layout.now);
  const key = (ball: LaidBall) => (event: KeyboardEvent) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPick(ball.ticketId); } };
  const { slots, clusters } = layout.labels;

  return (
    <div className="pletor-dashboard__linie-plot" data-pan style={{ width: layout.width, height: layout.height }}>
      <svg className="pletor-dashboard__linie-svg" width={layout.width} height={layout.height} role="img" aria-label="Řádky a kuličky Linie">
        {layout.rows.map((row) => (
          <line key={row.id} x1={0} y1={row.y} x2={layout.width} y2={row.y} stroke={row.color}
            strokeWidth={row.fixed ? 3 : 2} opacity={row.collapsed ? 0.25 : row.fixed ? 0.9 : 0.55} />
        ))}
        {nowX !== null && <line className="pletor-dashboard__linie-now" x1={nowX} y1={0} x2={nowX} y2={layout.height} />}
        <PlotMarksSvg layout={layout} selected={selected} layers={layers} onPickCommit={onPickCommit} onTip={setTip} />
        {layout.links.map((link) => {
          const id = `${link.ticketId}-${link.kind}-${link.toId}`;
          return <LinieLink key={id} link={link} id={`${gradientId}-${id.replace(/[^\w-]/g, "")}`} weak={link.kind === "planned" && !layers.plans && !mine(link.ticketId)} />;
        })}
        {layout.merges.map((merge) => (
          <circle key={merge.sha7} cx={merge.x} cy={merge.y} r={5} fill={merge.color}><title>{`${merge.sha7}: ${merge.title}`}</title></circle>
        ))}
        {layout.balls.map((ball) => {
          const slot = slots[ball.ticketId];
          const off = slot && labelOffsets(slot);
          const anchor = { textAnchor: labelAnchor(ball.x, ball, layout.width) };
          return (
            <g key={ball.ticketId} role="button" tabIndex={0} aria-label={`${ball.title}, ${ball.stateLabel}`} aria-pressed={mine(ball.ticketId)}
              className={`pletor-dashboard__linie-pick${lit && !lit.has(ball.ticketId) ? " pletor-dashboard__linie-pick--dim" : ""}`}
              onClick={() => onPick(ball.ticketId)} onKeyDown={key(ball)}
              onMouseEnter={() => setTip(ballTip(ball))} onMouseLeave={() => setTip(null)} onFocus={() => setTip(ballTip(ball))} onBlur={() => setTip(null)}>
              {mine(ball.ticketId) && <circle className="pletor-dashboard__linie-ring" cx={ball.x} cy={ball.y} r={16} />}
              <LinieBall glyph={ball.glyph} color={ball.color} toColor={ball.toColor !== ball.color ? ball.toColor : undefined} x={ball.x} y={ball.y} />
              {off && <text x={ball.x} y={ball.y + off.name} className="pletor-dashboard__linie-ball-name" style={anchor}>{ball.label}</text>}
              {off && <text x={ball.x} y={ball.y + off.state} className="pletor-dashboard__linie-ball-state" style={anchor}>{ball.stateLabel}</text>}
            </g>
          );
        })}
        {clusters.map((cluster) => {
          const ball = layout.balls.find((item) => item.ticketId === cluster.ids[0]);
          return ball && (
            <g key={cluster.ids[0]} role="button" tabIndex={0} className="pletor-dashboard__linie-pick" aria-label={`${ball.title} (popisek se nevešel)`}
              onClick={() => onPick(ball.ticketId)} onKeyDown={key(ball)}>
              <title>{ball.title}</title>
              <text x={ball.x} y={ball.y + 23} className="pletor-dashboard__linie-cluster">+1</text>
            </g>
          );
        })}
      </svg>
      <PlotMarksHtml layout={layout} selected={selected} layers={layers} />
      {tip && <LinieTip tip={tip} width={layout.width} />}
    </div>
  );
}
