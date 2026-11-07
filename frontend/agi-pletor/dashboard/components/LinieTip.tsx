import type { Tip } from "../logic/linie-tip";

const TIP_W = 260;

/** Bublina při najetí na kuličku nebo kostku commitu: nadpis, klíč · hodnota, patička „klik = detail“; nikdy nevyjede za plátno. */
export default function LinieTip({ tip, width }: { tip: Tip; width: number }) {
  return (
    <div className="pletor-dashboard__linie-tip" style={{ left: Math.min(tip.x + 16, width - TIP_W), top: Math.max(tip.y - 70, 4) }}>
      <strong className="pletor-dashboard__linie-tip-title">{tip.title}</strong>
      {tip.rows.map((row) => <span key={row.k}><span className="pletor-dashboard__linie-tip-key">{row.k}</span>{row.v}</span>)}
      <span className="pletor-dashboard__linie-tip-hint">klik = detail</span>
    </div>
  );
}
