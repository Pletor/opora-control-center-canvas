// Tenký pruh stavů: jeden úsek za každý koš karet (hotovo, ke schválení, selhalo, čeká na tebe, pracuje,
// čeká). Šířku úseku nese jen CSS proměnná `--w`; barvy jsou ve stylu podle modifikátoru.
import type { CSSProperties } from "react";
import { countSegments, type Counts } from "../logic/tower-model";

export default function TowerBar({ counts }: { counts: Counts }) {
  const segments = countSegments(counts);
  return (
    <div className="tower-bar" role="img" aria-label={segments.map((s) => s.count + " " + s.label).join(", ") || "Bez karet"}>
      {segments.map((s) => (
        <span key={s.key} className={"tower-bar__part tower-bar__part--" + s.key} title={s.count + " " + s.label}
          style={{ "--w": s.share + "%" } as CSSProperties} />
      ))}
    </div>
  );
}
