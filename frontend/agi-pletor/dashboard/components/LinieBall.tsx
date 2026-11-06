import type { CSSProperties } from "react";
import type { Fill } from "../logic/linie-board";

/** `toColor` = barva řádku, kam se práce začlení; bez ní (legenda stavů) se puntík cíle nekreslí. */
type Props = { fill: Fill | "plan"; color: string; toColor?: string; x: number; y: number; r?: number };

const AIMED: (Fill | "plan")[] = ["open", "done", "verify"];

/**
 * Glyf kuličky (SVG): jádro s výplní podle stavu, prstenec „hotovo“, červený střed blokace. Vnitřní puntík v barvě
 * cíle říká, kam práce směřuje; začleněná kulička nese cíl jako tenký prstenec. Sdílí ho editor i legenda.
 */
export default function LinieBall({ fill, color, toColor, x, y, r = 9 }: Props) {
  return (
    <g className={`pletor-dashboard__linie-ball pletor-dashboard__linie-ball--${fill}`} style={{ "--c": color, "--t": toColor ?? color } as CSSProperties}>
      {fill === "done" && <circle className="pletor-dashboard__linie-ball-ring" cx={x} cy={y} r={r + 4} />}
      {fill === "merged" && toColor && <circle className="pletor-dashboard__linie-ball-ring pletor-dashboard__linie-ball-ring--to" cx={x} cy={y} r={r + 3} />}
      <circle className="pletor-dashboard__linie-ball-core" cx={x} cy={y} r={r} />
      {fill === "blocked" && <circle className="pletor-dashboard__linie-ball-dot" cx={x} cy={y} r={r / 2.2} />}
      {fill === "verify" && !toColor &&<circle className="pletor-dashboard__linie-ball-dot" cx={x} cy={y} r={r / 3} />}
      {toColor && AIMED.includes(fill) && <circle className="pletor-dashboard__linie-ball-dot pletor-dashboard__linie-ball-dot--to" cx={x} cy={y} r={r / 3} />}
    </g>
  );
}
