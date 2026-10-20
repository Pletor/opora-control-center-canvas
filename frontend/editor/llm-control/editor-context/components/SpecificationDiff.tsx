import { specificationDiff } from "../logic/specification-diff";

export default function SpecificationDiff({ before, after }: { before: unknown; after: unknown }) {
  if (!before || !after) return <p>Původní nebo současné zadání není dostupné pro porovnání.</p>;
  const { changes, truncated } = specificationDiff(before, after);
  return <details>
    <summary>Rozdíly zadání ({changes.length}{truncated ? "+" : ""})</summary>
    <p>Počet označuje rozdílná pole nebo přidané či odebrané položky, nikoli počet úprav v čase.</p>
    {changes.length === 0 && <p>Zachycené zadání se nezměnilo.</p>}
    {changes.map(change => <section key={change.path}>
      <strong>{change.path}</strong>
      <div>Původní: <pre>{change.before === undefined ? "(chybělo)" : JSON.stringify(change.before, null, 2)}</pre></div>
      <div>Současné: <pre>{change.after === undefined ? "(odebráno)" : JSON.stringify(change.after, null, 2)}</pre></div>
    </section>)}
    {truncated && <p>Zobrazeno prvních 100 rozdílů. Úplná zadání jsou v uloženém výsledku a aktuálním kontextu karty.</p>}
  </details>;
}
