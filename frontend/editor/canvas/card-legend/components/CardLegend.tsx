// Legenda plátna 3: jednou dole na plátně, ne na každé kartě. Říká, co znamená barva rámu karty (druh z
// `card-face/logic/face-family.ts`), šipka vazby a vlajka milníku. Nic nepočítá, jen ukazuje klíč.
import "../styles/card-legend.css";

const ITEMS = [
  ["step", "Pracovní krok"], ["contract", "Kontrakt (rozhraní)"], ["verify", "Ověření / test"],
  ["decision", "Rozhodnutí"], ["flow", "Závislost / tok"], ["milestone", "Milník"],
] as const;

export default function CardLegend() {
  return (
    <div className="card-legend" data-oh-view="card-legend" aria-label="Legenda plátna">
      <span className="card-legend__title">Legenda:</span>
      {ITEMS.map(([key, label]) => (
        <span key={key} className="card-legend__item">
          <i className={"card-legend__mark card-legend__mark--" + key} aria-hidden="true" />{label}
        </span>
      ))}
    </div>
  );
}
