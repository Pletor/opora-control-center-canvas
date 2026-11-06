import type { CSSProperties } from "react";
import type { Fill } from "../logic/linie-board";

type Props = { fill: Fill | "plan"; color: string; x: number; y: number; r?: number };

/** Glyf kuličky (SVG): jádro s výplní podle stavu, prstenec „hotovo“, tečka ověření nebo červený střed blokace. Sdílí ho editor i legenda. */
export default function LinieBall({ fill, color, x, y, r = 9 }: Props) {
  return (
    <g className={`pletor-dashboard__linie-ball pletor-dashboard__linie-ball--${fill}`} style={{ "--c": color } as CSSProperties}>
      {fill === "done" && <circle className="pletor-dashboard__linie-ball-ring" cx={x} cy={y} r={r + 4} />}
      <circle className="pletor-dashboard__linie-ball-core" cx={x} cy={y} r={r} />
      {(fill === "verify" || fill === "blocked") && <circle className="pletor-dashboard__linie-ball-dot" cx={x} cy={y} r={fill === "verify" ? r / 3 : r / 2.2} />}
    </g>
  );
}
