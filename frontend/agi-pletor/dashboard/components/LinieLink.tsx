import type { LaidLink } from "../logic/linie-board";

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
export default function LinieLink({ link, id }: { link: LaidLink; id: string }) {
  const { from, to, fromColor, toColor } = link;
  if (link.kind === "follows") return <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={fromColor} strokeWidth={1.4} strokeDasharray="1 5" strokeLinecap="round" />;
  return (
    <g>
      <defs>
        <linearGradient id={id} gradientUnits="userSpaceOnUse" x1={from.x} y1={from.y} x2={to.x} y2={to.y}>
          <stop offset="0" stopColor={fromColor} /><stop offset="1" stopColor={toColor} />
        </linearGradient>
      </defs>
      {link.kind === "planned" ? <PlanLink link={link} stroke={`url(#${id})`} /> : (
        <>
          <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={`url(#${id})`} strokeWidth={2.8} />
          <circle cx={to.x} cy={to.y} r={5} fill={toColor} />
        </>
      )}
    </g>
  );
}
