import type { Board } from "../logic/linie-board";
import { glyphOf, legend } from "../logic/linie-glyph";
import LinieBall from "./LinieBall";

const GREY = "#6b8f7a";
const ERR = "#e07070";

/** Legenda pod editorem: každý glyf souhrnu s textem a počtem podle `summary.key` (`linie-glyph.ts`), plány, puntík cíle, druhy spojnic, pilulky PR, nasazení, opuštěná práce a worktree. */
export default function LinieLegend({ board }: { board: Board }) {
  const plans = board.balls.reduce((sum, b) => sum + b.links.filter((l) => l.kind === "planned").length, 0);
  return (
    <footer className="pletor-dashboard__linie-legend" aria-label="Legenda">
      {legend(board.balls).map((item) => (
        <span key={item.text} className="pletor-dashboard__linie-legend-item">
          <svg width={26} height={26} aria-hidden="true"><LinieBall glyph={item.glyph} color="#4ade80" toColor={item.glyph.key === "merged" ? "#60a5fa" : undefined} x={13} y={13} r={6} /></svg>
          {item.text} <span className="pletor-dashboard__linie-legend-count">{item.count}</span>
        </span>
      ))}
      <span className="pletor-dashboard__linie-legend-item">
        <svg width={26} height={26} aria-hidden="true"><circle className="pletor-dashboard__linie-plan-end" cx={13} cy={13} r={7} stroke="#4ade80" /></svg>
        plán <span className="pletor-dashboard__linie-legend-count">{plans}</span>
      </span>
      <span className="pletor-dashboard__linie-legend-item">
        <svg width={26} height={26} aria-hidden="true"><LinieBall glyph={glyphOf("wip")} color="#4ade80" toColor="#60a5fa" x={13} y={13} r={6} /></svg>puntík = kam se začlení
      </span>
      <span className="pletor-dashboard__linie-legend-item">
        <svg width={34} height={8} aria-hidden="true"><line x1={0} y1={4} x2={34} y2={4} stroke={GREY} strokeWidth={1.4} strokeDasharray="1 4" strokeLinecap="round" /></svg>návaznost práce
      </span>
      <span className="pletor-dashboard__linie-legend-item">
        <svg width={34} height={8} aria-hidden="true"><line x1={0} y1={4} x2={28} y2={4} stroke={GREY} strokeWidth={1.6} strokeDasharray="6 4" /><polygon points="34,4 27,0 27,8" fill={GREY} /></svg>plán začlenění
      </span>
      <span className="pletor-dashboard__linie-legend-item">
        <svg width={34} height={10} aria-hidden="true"><line x1={0} y1={5} x2={28} y2={5} stroke="#cfe3d6" strokeWidth={2.6} /><circle cx={29} cy={5} r={4} fill="#cfe3d6" /></svg>skutečný merge
      </span>
      <span className="pletor-dashboard__linie-legend-item"><span className="pletor-dashboard__linie-pr pletor-dashboard__linie-pr--open pletor-dashboard__linie-pr--static">PR #350 · otevřen</span>potvrzeno GitHubem</span>
      <span className="pletor-dashboard__linie-legend-item"><span className="pletor-dashboard__linie-pr pletor-dashboard__linie-pr--unverified pletor-dashboard__linie-pr--static">PR · neověřeno</span>zdroj nedostupný</span>
      <span className="pletor-dashboard__linie-legend-item"><span className="pletor-dashboard__linie-taglabel pletor-dashboard__linie-taglabel--deploy pletor-dashboard__linie-pr--static">prod@d8da63b</span>nasazení potvrzené prostředím</span>
      <span className="pletor-dashboard__linie-legend-item">
        <svg width={30} height={16} aria-hidden="true"><rect x={4} y={3} width={6} height={10} rx={1} fill="rgba(214,96,96,.25)" stroke={ERR} strokeWidth={1.5} /><path d="M10 8 L22 2" stroke={ERR} strokeDasharray="3 3" fill="none" /></svg>opuštěná práce
      </span>
      <span className="pletor-dashboard__linie-legend-item">⌂ worktree · agent od–do</span>
    </footer>
  );
}
