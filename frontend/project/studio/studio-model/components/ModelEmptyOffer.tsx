/** Nabídka nad prázdným modelem domény (docs/studio.md §4): navrhnout model z architektury OPORY (jen návrh, člověk
 * ho zkontroluje a uloží) nebo začít s prázdným plátnem. Volbu hlásí rodiči. */
export default function ModelEmptyOffer({ domainName, cards, onPropose, onEmpty }: { domainName: string; cards: number; onPropose: () => void; onEmpty: () => void }) {
  return <section className="studio-model__offer" aria-label="Prázdný model domény" data-testid="studio-model-offer">
    <h2 className="studio-model__offer-title">Doména {domainName} zatím nemá technický model</h2>
    <p className="studio-model__offer-text">Model je výpočet, ne měření: popisuje, jak by komponenty domény spolu mluvily a kolik toho unesou.
      Návrh z architektury vytvoří komponentu pro každou kartu OPORY ({cards}) a vazby podle toho, co nesou; nic se neuloží, dokud nestisknete Uložit.</p>
    <div className="studio-model__offer-actions">
      <button type="button" className="studio-model__save" data-testid="studio-model-propose" onClick={onPropose} disabled={!cards}>Navrhnout z architektury</button>
      <button type="button" className="studio-model__tool studio-model__tool--text" data-testid="studio-model-start-empty" onClick={onEmpty}>Začít prázdný</button>
    </div>
  </section>;
}
