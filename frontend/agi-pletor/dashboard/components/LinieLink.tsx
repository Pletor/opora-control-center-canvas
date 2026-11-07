import type { LaidLink } from "../logic/linie-board";

/** Plán: čárkovaná přímka končí 13 px před cílem šipkou a přerušovaným kroužkem, aby nikdy nevypadala jako skutečný
 * merge (plná křivka s bodem). Slabý plán (mimo vrstvu a bez výběru) je na .25 a bez popisku. */
function PlanLink({ link, stroke, weak }: { link: LaidLink; stroke: string; weak: boolean }) {
  const { from, to, toColor } = link;
  const dx = to.x - from.x, dy = to.y - from.y, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
  const ex = to.x - ux * 13, ey = to.y - uy * 13, bx = ex - ux * 8, by = ey - uy * 8;
  return (
    <g opacity={weak ? 0.25 : 1}>
      <path className="pletor-dashboard__linie-plan-line" d={`M${from.x} ${from.y} L${bx} ${by}`} stroke={stroke} />
      <polygon points={`${ex},${ey} ${bx - uy * 4},${by + ux * 4} ${bx + uy * 4},${by - ux * 4}`} fill={toColor} />
      {link.openEnd && <circle className="pletor-dashboard__linie-plan-end" cx={to.x} cy={to.y} r={7} stroke={toColor} />}
      {!weak && <text x={from.x + dx / 2} y={from.y + dy / 2 - 4} className={`pletor-dashboard__linie-plan${link.label.startsWith("blokováno") ? " pletor-dashboard__linie-plan--blocked" : ""}`}>{link.label}</text>}
    </g>
  );
}

/** Spojnice teče gradientem od barvy zdroje k barvě cíle (`userSpaceOnUse`, aby fungoval i na vodorovné čáře). Merge
 * je Bezierova křivka z kuličky na osu cíle v čase merge s plným bodem r 5; nakreslí se jednou (`pathLength` 1). */
export default function LinieLink({ link, id, weak }: { link: LaidLink; id: string; weak: boolean }) {
  const { from, to, fromColor, toColor } = link;
  if (link.kind === "follows") return <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={fromColor} strokeWidth={1.4} strokeDasharray="1 5" strokeLinecap="round" />;
  return (
    <g>
      <defs>
        <linearGradient id={id} gradientUnits="userSpaceOnUse" x1={from.x} y1={from.y} x2={to.x} y2={to.y}>
          <stop offset="0" stopColor={fromColor} /><stop offset="1" stopColor={toColor} />
        </linearGradient>
      </defs>
      {link.kind === "planned" ? <PlanLink link={link} stroke={`url(#${id})`} weak={weak} /> : (
        <>
          <path className="pletor-dashboard__linie-merge" pathLength={1} stroke={`url(#${id})`}
            d={`M${from.x} ${from.y} C ${from.x + 40} ${from.y}, ${to.x - 40} ${to.y}, ${to.x} ${to.y}`} />
          <circle cx={to.x} cy={to.y} r={5} fill={toColor} />
        </>
      )}
    </g>
  );
}
