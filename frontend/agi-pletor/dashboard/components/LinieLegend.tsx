import { legend, type Board } from "../logic/linie-board";
import LinieBall from "./LinieBall";

const GREY = "#6b8f7a";

/** Legenda pod editorem: každá výplň s textem a počtem, pak tři druhy spojnic. */
export default function LinieLegend({ board }: { board: Board }) {
  return (
    <footer className="pletor-dashboard__linie-legend" aria-label="Legenda">
      {legend(board).map((item) => (
        <span key={item.fill} className="pletor-dashboard__linie-legend-item">
          <svg width={26} height={26} aria-hidden="true">
            {item.fill === "plan"
              ? <circle className="pletor-dashboard__linie-plan-end" cx={13} cy={13} r={7} stroke="#4ade80" />
              : <LinieBall fill={item.fill} color="#4ade80" x={13} y={13} r={6} />}
          </svg>
          {item.text} <span className="pletor-dashboard__linie-legend-count">{item.count}</span>
        </span>
      ))}
      <span className="pletor-dashboard__linie-legend-item">
        <svg width={34} height={8} aria-hidden="true"><line x1={0} y1={4} x2={34} y2={4} stroke={GREY} strokeWidth={1.4} strokeDasharray="1 4" strokeLinecap="round" /></svg>návaznost práce
      </span>
      <span className="pletor-dashboard__linie-legend-item">
        <svg width={34} height={8} aria-hidden="true"><line x1={0} y1={4} x2={28} y2={4} stroke={GREY} strokeWidth={1.6} strokeDasharray="6 4" /><polygon points="34,4 27,0 27,8" fill={GREY} /></svg>plán začlenění
      </span>
      <span className="pletor-dashboard__linie-legend-item">
        <svg width={34} height={10} aria-hidden="true"><line x1={0} y1={5} x2={28} y2={5} stroke="#cfe3d6" strokeWidth={2.6} /><circle cx={29} cy={5} r={4} fill="#cfe3d6" /></svg>skutečný merge
      </span>
    </footer>
  );
}
