import { useState, type KeyboardEvent } from "react";
import { TYPE_LABEL, type BoardLayout, type LaidBall, type LaidLink, type LaidRow } from "../logic/linie-board";
import LinieBall from "./LinieBall";

type Props = {
  layout: BoardLayout; selected: string;
  onPick: (ticketId: string) => void;
  onRename: (rowId: string, name: string) => void;
  onFold: (rowId: string, collapsed: boolean) => void;
};

const TIP_W = 260;

/** Plán: čárkovaná čára končí šipkou před cílem, aby nikdy nevypadala jako skutečný merge (plná čára s bodem). */
function PlanLink({ link }: { link: LaidLink }) {
  const { from, to, color } = link;
  const dx = to.x - from.x, dy = to.y - from.y, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
  const ex = to.x - ux * 13, ey = to.y - uy * 13, bx = ex - ux * 8, by = ey - uy * 8;
  return (
    <g>
      <line x1={from.x} y1={from.y} x2={bx} y2={by} stroke={color} strokeWidth={1.6} strokeDasharray="6 4" />
      <polygon points={`${ex},${ey} ${bx - uy * 4},${by + ux * 4} ${bx + uy * 4},${by - ux * 4}`} fill={color} />
      <text x={from.x + dx * 0.45} y={from.y + dy * 0.45 - 6} fill={color} className="pletor-dashboard__linie-plan">plán</text>
      {link.openEnd && <circle className="pletor-dashboard__linie-plan-end" cx={to.x} cy={to.y} r={7} stroke={color} />}
    </g>
  );
}

function Link({ link }: { link: LaidLink }) {
  const { from, to, color } = link;
  if (link.kind === "planned") return <PlanLink link={link} />;
  if (link.kind === "follows") return <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={color} strokeWidth={1.4} strokeDasharray="1 5" strokeLinecap="round" />;
  return (
    <g>
      <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={color} strokeWidth={2.8} />
      <circle cx={to.x} cy={to.y} r={5} fill={color} />
    </g>
  );
}

/**
 * Editor Linie: vlevo hlavičky řádků (název, typ, větev, cíl; šipka sbalí, dvojklik přejmenuje), vpravo SVG s časem
 * zleva doprava, kuličkami a spojnicemi. Hover ukáže vlastní bublinu, klik hlásí `onPick`. Zápisy hlásí rodiči.
 */
export default function LinieBoard({ layout, selected, onPick, onRename, onFold }: Props) {
  const [tip, setTip] = useState<LaidBall | null>(null);
  const [editing, setEditing] = useState("");
  const [value, setValue] = useState("");
  const commit = (row: LaidRow) => {
    setEditing("");
    if (value.trim() && value.trim() !== row.name) onRename(row.id, value.trim());
  };
  const key = (ball: LaidBall) => (event: KeyboardEvent) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPick(ball.ticketId); } };

  return (
    <div className="pletor-dashboard__linie-board">
      <div className="pletor-dashboard__linie-rows">
        <div className="pletor-dashboard__linie-axis">řádek · větev · cíl</div>
        {layout.rows.map((row) => (
          <div key={row.id} className="pletor-dashboard__linie-row" style={{ minHeight: row.height, height: row.height }}>
            <div className="pletor-dashboard__linie-row-top">
              {row.fixed
                ? <span className="pletor-dashboard__linie-lock" title="pevný řádek">■</span>
                : <button type="button" className="pletor-dashboard__linie-fold" aria-expanded={!row.collapsed} aria-label={`${row.collapsed ? "Rozbalit" : "Sbalit"} ${row.name}`}
                    onClick={() => onFold(row.id, !row.collapsed)}>{row.collapsed ? "▸" : "▾"}</button>}
              {editing === row.id ? (
                <input className="pletor-dashboard__linie-rename" aria-label="Nový název řádku" value={value} autoFocus onChange={(event) => setValue(event.target.value)}
                  onBlur={() => commit(row)} onKeyDown={(event) => { if (event.key === "Enter") commit(row); if (event.key === "Escape") setEditing(""); }} />
              ) : (
                <span className="pletor-dashboard__linie-row-name" style={{ color: row.color }} title={row.fixed ? row.name : "dvojklik = přejmenovat"}
                  onDoubleClick={row.fixed ? undefined : () => { setEditing(row.id); setValue(row.name); }}>{row.name}</span>
              )}
              <span className="pletor-dashboard__linie-chip">{TYPE_LABEL[row.type]}</span>
            </div>
            <div className={`pletor-dashboard__linie-meta${row.branch ? "" : " pletor-dashboard__linie-meta--none"}`}>{row.branchText}</div>
            {!row.collapsed && (row.fixed
              ? <div className="pletor-dashboard__linie-meta">{row.mappingText}</div>
              : <div className="pletor-dashboard__linie-meta">z {row.baseBranch || "—"} → cíl {row.target || "zatím neurčeno"}</div>)}
          </div>
        ))}
      </div>

      <div className="pletor-dashboard__linie-canvas">
        <div className="pletor-dashboard__linie-ticks" style={{ width: layout.width }}>
          {layout.ticks.map((tick) => <span key={tick.text} className="pletor-dashboard__linie-tick" style={{ left: tick.x }}>{tick.text}</span>)}
        </div>
        <div className="pletor-dashboard__linie-plot" style={{ width: layout.width, height: layout.height }}>
          <svg className="pletor-dashboard__linie-svg" width={layout.width} height={layout.height} role="img" aria-label="Řádky a kuličky Linie">
            {layout.rows.map((row) => (
              <line key={row.id} x1={0} y1={row.y} x2={layout.width} y2={row.y} stroke={row.color}
                strokeWidth={row.fixed ? 3 : 2} opacity={row.collapsed ? 0.25 : row.fixed ? 0.9 : 0.55} />
            ))}
            {layout.links.map((link, index) => <Link key={index} link={link} />)}
            {layout.merges.map((merge) => (
              <circle key={merge.sha7} cx={merge.x} cy={merge.y} r={5} fill={merge.color}><title>{`merge ${merge.sha7}: ${merge.title}`}</title></circle>
            ))}
            {layout.balls.map((ball) => (
              <g key={ball.ticketId} role="button" tabIndex={0} aria-label={`${ball.title}, ${ball.stateLabel}`}
                className={`pletor-dashboard__linie-pick${ball.ticketId === selected ? " pletor-dashboard__linie-pick--selected" : ""}`}
                onClick={() => onPick(ball.ticketId)} onKeyDown={key(ball)}
                onMouseEnter={() => setTip(ball)} onMouseLeave={() => setTip(null)} onFocus={() => setTip(ball)} onBlur={() => setTip(null)}>
                <LinieBall fill={ball.fill} color={ball.color} x={ball.x} y={ball.y} />
                <text x={ball.x} y={ball.y + 26} className="pletor-dashboard__linie-ball-name">{ball.label}</text>
                <text x={ball.x} y={ball.y + 39} className="pletor-dashboard__linie-ball-state">{ball.stateLabel}</text>
              </g>
            ))}
          </svg>
          {tip && (
            <div className="pletor-dashboard__linie-tip" style={{ left: Math.min(tip.x + 16, layout.width - TIP_W), top: Math.max(tip.y - 70, 4) }}>
              <strong className="pletor-dashboard__linie-tip-title">{tip.hover.title}</strong>
              <span><span className="pletor-dashboard__linie-tip-key">stav</span>{tip.hover.state}</span>
              <span><span className="pletor-dashboard__linie-tip-key">vznik</span>{tip.hover.created}</span>
              <span><span className="pletor-dashboard__linie-tip-key">začlenění</span>{tip.hover.merged}</span>
              <span><span className="pletor-dashboard__linie-tip-key">commity|PR|merge</span>{tip.hover.counts}</span>
              <span><span className="pletor-dashboard__linie-tip-key">větev</span>{tip.hover.branch}</span>
              <span className="pletor-dashboard__linie-tip-hint">klik = detail</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
