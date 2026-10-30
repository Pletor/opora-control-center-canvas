// Malý odznak měřáku na pilulce karty ve Velínu: štítek složitosti (XS–XL, „?“), % kroků a riziko, když není
// standard. Jen čte hotový model (`gaugeBadge`); celý popis je v titulku, klik patří pilulce.
import { riskLabel, type GaugeBadge } from "../logic/card-gauge-badge";
import "../styles/card-gauge-badge.css";

export default function CardGaugeBadge({ badge }: { badge: GaugeBadge | null }) {
  if (!badge) return null;
  return (
    <span className={"card-gauge" + (badge.thin ? " card-gauge--thin" : "")} title={badge.title}
      data-oh-gauge-label={badge.label} data-oh-gauge-steps={badge.steps ?? ""} data-oh-gauge-risk={badge.risk ?? "standard"}>
      <b className="card-gauge__label">{badge.label}</b>
      {badge.steps !== null && <span className="card-gauge__steps">{badge.steps} %</span>}
      {badge.risk && <span className={"card-gauge__risk card-gauge__risk--" + badge.risk} aria-label={riskLabel(badge.risk)}>
        {badge.risk === "critical" ? "!!" : "!"}</span>}
    </span>
  );
}
