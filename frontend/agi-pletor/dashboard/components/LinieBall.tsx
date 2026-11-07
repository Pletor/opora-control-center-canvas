import type { CSSProperties } from "react";
import type { Glyph } from "../logic/linie-glyph";
import "../styles/pletor-dashboard-linie-ball.css";

/** `toColor` = barva řádku, kam se práce začlení; bez ní (legenda) se puntík cíle nekreslí. */
type Props = { glyph: Glyph; color: string; toColor?: string; x: number; y: number; r?: number };

/**
 * Glyf kuličky (SVG) ze `summary.key` (`linie-glyph.ts`, prototyp „Linie v3“): jádro ghost/open/full/plain/parked,
 * hal u čekajících na člověka, žlutý prstenec zastaralého přijetí, červený střed bloku, puntík cíle. Začleněná
 * kulička se plní barvou cíle. Sdílí ho editor i legenda.
 */
export default function LinieBall({ glyph, color, toColor, x, y, r = 9 }: Props) {
  const fill = glyph.key === "merged" && toColor ? toColor : color;
  return (
    <g className={`linie-plot__ball linie-plot__ball--${glyph.key}`} style={{ "--c": fill, "--t": toColor ?? color } as CSSProperties}>
      {glyph.halo && <circle className="linie-plot__ball-halo" cx={x} cy={y} r={r + 4} />}
      {glyph.staleRing && <circle className="linie-plot__ball-stale" cx={x} cy={y} r={r + 4} />}
      <circle className={`linie-plot__ball-core linie-plot__ball-core--${glyph.core}`} cx={x} cy={y} r={r} />
      {toColor && glyph.aim && <circle className="linie-plot__ball-aim" cx={x} cy={y} r={r * 0.36} />}
      {glyph.blocked && <circle className="linie-plot__ball-block" cx={x} cy={y} r={r * 0.45} />}
    </g>
  );
}
