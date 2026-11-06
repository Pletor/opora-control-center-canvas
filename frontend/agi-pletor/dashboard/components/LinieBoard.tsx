import { useId, useRef, useState, type KeyboardEvent } from "react";
import { ROW_THIN, TYPE_LABEL, type BoardLayout, type LaidBall, type LaidLink, type LaidRow } from "../logic/linie-board";
import LinieBall from "./LinieBall";

type Props = {
  layout: BoardLayout; selected: string;
  /** Text chipu sbalených řádků („N větví · M kuliček“) podle id řádku. */
  chips: Record<string, string>;
  onPick: (ticketId: string) => void;
  onRename: (rowId: string, name: string) => void;
  onFold: (rowId: string, collapsed: boolean) => void;
  onFocus: (branch: string) => void;
};

const TIP_W = 260;
const CLICK_MS = 250; // jednoklik čeká, jestli nepřijde dvojklik (přejmenování), jinak by zaměření přeskládalo řádky pod myší

/** Plán: čárkovaná čára končí šipkou před cílem, aby nikdy nevypadala jako skutečný merge (plná čára s bodem). */
function PlanLink({ link, stroke }: { link: LaidLink; stroke: string }) {
  const { from, to, toColor } = link;
  const dx = to.x - from.x, dy = to.y - from.y, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
  const ex = to.x - ux * 13, ey = to.y - uy * 13, bx = ex - ux * 8, by = ey - uy * 8;
  return (
    <g>
      <line x1={from.x} y1={from.y} x2={bx} y2={by} stroke={stroke} strokeWidth={1.6} strokeDasharray="6 4" />
      <polygon points={`${ex},${ey} ${bx - uy * 4},${by + ux * 4} ${bx + uy * 4},${by - ux * 4}`} fill={toColor} />
      <text x={from.x + dx * 0.45} y={from.y + dy * 0.45 - 6} fill={link.fromColor} className="pletor-dashboard__linie-plan">plán</text>
      {link.openEnd && <circle className="pletor-dashboard__linie-plan-end" cx={to.x} cy={to.y} r={7} stroke={toColor} />}
    </g>
  );
}

/** Plán i merge tečou gradientem od barvy zdroje k barvě cíle (`userSpaceOnUse`, aby fungoval i na vodorovné čáře). */
function Link({ link, id }: { link: LaidLink; id: string }) {
  const { from, to, fromColor, toColor } = link;
  if (link.kind === "follows") return <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={fromColor} strokeWidth={1.4} strokeDasharray="1 5" strokeLinecap="round" />;
  const gradient = (
    <linearGradient id={id} gradientUnits="userSpaceOnUse" x1={from.x} y1={from.y} x2={to.x} y2={to.y}>
      <stop offset="0" stopColor={fromColor} /><stop offset="1" stopColor={toColor} />
    </linearGradient>
  );
  return (
    <g>
      <defs>{gradient}</defs>
      {link.kind === "planned" ? <PlanLink link={link} stroke={`url(#${id})`} /> : (
        <>
          <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={`url(#${id})`} strokeWidth={2.8} />
          <circle cx={to.x} cy={to.y} r={5} fill={toColor} />
        </>
      )}
    </g>
  );
}

/**
 * Editor Linie: vlevo hlavičky řádků (název, typ, větev, cíl; šipka sbalí podstrom, klik na název zaměří větev,
 * dvojklik přejmenuje), vpravo SVG s časem zleva doprava, kuličkami a spojnicemi. Hover ukáže vlastní bublinu,
 * klik na kuličku hlásí `onPick`. Zápisy a zaměření hlásí rodiči.
 */
export default function LinieBoard({ layout, selected, chips, onPick, onRename, onFold, onFocus }: Props) {
  const gradientId = `linie-g${useId().replace(/[^\w-]/g, "")}`; // dvojtečky z useId by v url(#…) neprošly
  const clickTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [tip, setTip] = useState<LaidBall | null>(null);
  const [editing, setEditing] = useState("");
  const [value, setValue] = useState("");
  const commit = (row: LaidRow) => {
    setEditing("");
    if (value.trim() && value.trim() !== row.name) onRename(row.id, value.trim());
  };
  // Automatický řádek nese jen část jména za rodičem (feat/velin-linie-strom → „strom“): rodiče čte oko ze stromu, celá větev je v meta řádku.
  const label = (row: LaidRow) => (row.auto && row.parent && row.branch.startsWith(`${row.parent}-`) ? row.branch.slice(row.parent.length + 1) : row.name || row.branch);
  const renamable = (row: LaidRow) => !row.fixed && !row.git && !row.auto;
  const chip = (row: LaidRow) => (row.planned ? "plánováno · bez větve" : row.git ? "z gitu" : row.auto ? "z větve" : TYPE_LABEL[row.type]);
  const key = (ball: LaidBall) => (event: KeyboardEvent) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPick(ball.ticketId); } };

  return (
    <div className="pletor-dashboard__linie-board">
      <div className="pletor-dashboard__linie-rows">
        <div className="pletor-dashboard__linie-axis">řádek · větev · cíl</div>
        {layout.rows.map((row) => (
          <div key={row.id} className={`pletor-dashboard__linie-row pletor-dashboard__linie-row--depth-${Math.min(row.depth, 4)}`} style={{ minHeight: row.height, height: row.height }}>
            <div className="pletor-dashboard__linie-row-top">
              <button type="button" className="pletor-dashboard__linie-fold" aria-expanded={!row.collapsed} aria-label={`${row.collapsed ? "Rozbalit" : "Sbalit"} ${label(row)}`}
                onClick={() => onFold(row.id, !row.collapsed)}>{row.collapsed ? "▸" : "▾"}</button>
              {(row.fixed || row.git) && <span className="pletor-dashboard__linie-lock" title={row.git ? "větev z gitu bez úkolu" : "pevný řádek"}>{row.git ? "⎇" : "■"}</span>}
              {editing === row.id ? (
                <input className="pletor-dashboard__linie-rename" aria-label="Nový název řádku" value={value} autoFocus onChange={(event) => setValue(event.target.value)}
                  onBlur={() => commit(row)} onKeyDown={(event) => { if (event.key === "Enter") commit(row); if (event.key === "Escape") setEditing(""); }} />
              ) : (
                <span className={`pletor-dashboard__linie-row-name${row.branch ? " pletor-dashboard__linie-row-name--focusable" : ""}`} style={{ color: row.color }}
                  title={[row.branch && "klik = zaměřit", renamable(row) && "dvojklik = přejmenovat"].filter(Boolean).join(", ") || label(row)}
                  role={row.branch ? "button" : undefined} tabIndex={row.branch ? 0 : undefined}
                  onKeyDown={row.branch ? (event) => { if (event.key === "Enter") onFocus(row.branch); } : undefined}
                  onClick={row.branch ? () => { clearTimeout(clickTimer.current); clickTimer.current = setTimeout(() => onFocus(row.branch), CLICK_MS); } : undefined}
                  onDoubleClick={renamable(row) ? () => { clearTimeout(clickTimer.current); setEditing(row.id); setValue(row.name); } : undefined}>{label(row)}</span>
              )}
              <span className="pletor-dashboard__linie-chip">{row.collapsed && chips[row.id] ? chips[row.id] : chip(row)}</span>
            </div>
            {row.height === ROW_THIN ? null : <div className={`pletor-dashboard__linie-meta${row.branch ? "" : " pletor-dashboard__linie-meta--none"}`}>{row.branchText}</div>}
            {!row.collapsed && row.height !== ROW_THIN && (row.fixed
              ? <div className="pletor-dashboard__linie-meta">{row.mappingText}</div>
              : <div className="pletor-dashboard__linie-meta">z {row.parent || row.baseBranch || "—"} → cíl {row.target || "zatím neurčeno"}</div>)}
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
            {layout.links.map((link, index) => <Link key={index} link={link} id={`${gradientId}-${index}`} />)}
            {layout.merges.map((merge) => (
              <circle key={merge.sha7} cx={merge.x} cy={merge.y} r={5} fill={merge.color}><title>{`${merge.sha7}: ${merge.title}`}</title></circle>
            ))}
            {layout.balls.map((ball) => (
              <g key={ball.ticketId} role="button" tabIndex={0} aria-label={`${ball.title}, ${ball.stateLabel}`}
                className={`pletor-dashboard__linie-pick${ball.ticketId === selected ? " pletor-dashboard__linie-pick--selected" : ""}`}
                onClick={() => onPick(ball.ticketId)} onKeyDown={key(ball)}
                onMouseEnter={() => setTip(ball)} onMouseLeave={() => setTip(null)} onFocus={() => setTip(ball)} onBlur={() => setTip(null)}>
                <LinieBall fill={ball.fill} color={ball.color} toColor={ball.toColor !== ball.color ? ball.toColor : undefined} x={ball.x} y={ball.y} />
                <text x={ball.x} y={ball.y + 26} className="pletor-dashboard__linie-ball-name">{ball.label}</text>
                <text x={ball.x} y={ball.y + 39} className="pletor-dashboard__linie-ball-state">{ball.stateLabel}</text>
              </g>
            ))}
          </svg>
          {tip && (
            <div className="pletor-dashboard__linie-tip" style={{ left: Math.min(tip.x + 16, layout.width - TIP_W), top: Math.max(tip.y - 70, 4) }}>
              <strong className="pletor-dashboard__linie-tip-title">{tip.hover.title}</strong>
              {tip.hover.mark && <span><span className="pletor-dashboard__linie-tip-key">značka</span>{tip.hover.mark}</span>}
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
