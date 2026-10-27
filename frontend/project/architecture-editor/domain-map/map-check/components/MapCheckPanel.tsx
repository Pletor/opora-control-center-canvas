import type { MapCheckGroup, MapCheckTarget } from "../logic/map-check";
import "../styles/map-check.css";

/** Díry mapy jedné domény nad cestami zákazníka: skupina na pravidlo (popisek, počet, rada) se sbalitelným seznamem zpráv
 * z backendu. Klik na zprávu hlásí rodiči cíl (`onSelect`); nález bez místa v grafu je jen text. Nic neukládá. */
export default function MapCheckPanel({ groups, onSelect }: { groups: MapCheckGroup[]; onSelect: (target: MapCheckTarget) => void }) {
  const total = groups.reduce((sum, group) => sum + group.items.length, 0);
  return <section className="map-check" data-testid="architecture-map-check">
    <header className="map-check__head">
      <h3 className="map-check__title">Díry mapy</h3>
      <span className={"map-check__total" + (total ? "" : " map-check__total--clean")}>{total || "✓"}</span>
    </header>
    {!total ? <p className="map-check__clean">Mapa je bez děr.</p>
      : <ul className="map-check__groups">
          {groups.map((group) => <li key={group.rule} className="map-check__group">
            <details>
              <summary className="map-check__summary" data-testid={"architecture-map-check-" + group.rule}>
                <span className="map-check__label">{group.label}</span>
                <span className="map-check__count">{group.items.length}</span>
              </summary>
              <p className="map-check__advice">{group.advice}</p>
              <ol className="map-check__list">
                {group.items.map(({ finding, target, place }, index) => <li key={index} className="map-check__item">
                  {target ? <button type="button" className="map-check__link" onClick={() => onSelect(target)}>{place && <b className="map-check__place">{place}</b>}{finding.message}</button>
                    : <span className="map-check__note">{place && <b className="map-check__place">{place}</b>}{finding.message}</span>}
                </li>)}
              </ol>
            </details>
          </li>)}
        </ul>}
  </section>;
}
