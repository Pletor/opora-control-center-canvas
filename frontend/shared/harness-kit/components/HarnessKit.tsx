import { harnessChanged, harnessOf } from '../logic/harness-kit';
import '../styles/harness-kit.css';

/** Show the complete accepted payload, including executable text and capability requirements. */
export default function HarnessKit({ before, after, mode = 'working' }: {
  before?: object | null; after?: object | null; mode?: 'accepted' | 'working' | 'diff';
}) {
  const old = harnessOf(before), next = harnessOf(after);
  if (old === null && next === null) return null;
  const changed = harnessChanged(before, after);
  const payload = (label: string, value: unknown) => <div className="harness-kit__version">
    <h5>{label}</h5>
    {value === null ? <p>Bez připnuté výbavy.</p> : <pre className="harness-kit__content">{JSON.stringify(value, null, 2)}</pre>}
  </div>;
  return <section className="harness-kit" aria-label="Výbava Harness" data-oh-spec-field="harness" data-oh-diff={changed ? 'changed' : 'same'}>
    <h4>Výbava Harness · {changed ? 'změněno' : 'beze změny'}</h4>
    <p>Obsah a verze prostředků pro běh. Požadavky vyžadují dostupný nástroj; tento seznam neuděluje oprávnění.</p>
    {mode === 'diff' && changed ? <div className="harness-kit__comparison">
      {payload('Přijatá výbava', old)}{payload('Navržená výbava', next)}
    </div> : payload(mode === 'accepted' ? 'Přijatá výbava' : 'Pracovní výbava', mode === 'accepted' ? old : next)}
  </section>;
}
