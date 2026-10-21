import type { ExecutionObservationsView } from "../logic/use-execution-observations";
import { formatUsdCents, hasProviderUsage, observationStatus, observedAt, type ObservationItem } from "../logic/observations";
import "../styles/execution-observations.css";

const number = (value: number) => new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 3 }).format(value);
function Usage({ item }: { item: ObservationItem }) {
  const usage = item.observation?.cumulative;
  if (!usage || !hasProviderUsage(item)) return <p>Spotřeba nedoložena. Broker zatím nedoložil čtení konkrétní session.</p>;
  return <dl className="execution-observations__usage">
    <dt>Vstupní tokeny</dt><dd>{number(usage.inputTokens)}</dd>
    <dt>Výstupní tokeny</dt><dd>{number(usage.outputTokens)}</dd>
    <dt>Načtené cache tokeny</dt><dd>{number(usage.cacheReadInputTokens)}</dd>
    <dt>Vytvořené cache tokeny · 5 min</dt><dd>{number(usage.cacheCreation5mTokens)}</dd>
    <dt>Vytvořené cache tokeny · 1 h</dt><dd>{number(usage.cacheCreation1hTokens)}</dd>
    <dt>Aktivní sekundy podle poskytovatele</dt><dd>{number(usage.activeSeconds)}</dd>
    <dt>Ceníková spotřeba</dt><dd>{formatUsdCents(usage.listCostCents)} podle ceníku · není faktura</dd>
  </dl>;
}
function Summary({ item }: { item: ObservationItem }) {
  const usage = item.observation?.cumulative;
  return <>
    <strong>{observationStatus(item)}</strong>
    <span>Karta <code>{item.intent.nodeId}</code> · běh <code>{item.intent.executionId}</code> · epocha {item.intent.epoch}</span>
    <span>{item.observation ? observedAt(item.observation.observedAt) : "Založeno " + observedAt(item.intent.createdAt)}</span>
    <span>{hasProviderUsage(item) && usage ? formatUsdCents(usage.listCostCents) + " podle ceníku" : "Spotřeba nedoložena"}</span>
    {item.listBudgetExceeded && <strong className="execution-observations__warning">Překročen ceníkový rozpočet</strong>}
  </>;
}
function compactTitle(item: ObservationItem, cards: { id: string; name: string }[]) {
  return cards.find(card => card.id === item.intent.nodeId)?.name ?? item.intent.nodeId;
}
function Compact({ model, cards, onSelect, onViewAll }: {
  model: ExecutionObservationsView; cards: { id: string; name: string }[]; onSelect?: (executionId: string, intentId: string) => void; onViewAll?: () => void;
}) {
  const exceeded = model.items.filter(item => item.listBudgetExceeded).length;
  const unknown = model.items.filter(item => !hasProviderUsage(item)).length;
  const rows = model.items.slice(0, 2);
  return <section className="execution-observations execution-observations--compact" aria-label="Pozorování běhů" aria-busy={model.busy}>
    <header className="execution-observations__head"><h2>Pozorování běhů</h2><span>{model.busy ? "Načítám…" : `${model.items.length} načteno`}</span>
      <button type="button" onClick={model.refresh} disabled={model.busy}>Obnovit</button></header>
    {model.error ? <p className="execution-observations__warning" role="alert">Pozorování nejsou dostupná: {model.error}</p> : <>
        {!model.observerConfigured && <p>Broker pozorování není nakonfigurován.</p>}
        {!!model.items.length && <>
          <p className="execution-observations__compact-source">API poskytovatele doložené brokerem · ceníková spotřeba, nikoli faktura.</p>
          <p className="execution-observations__compact-counts">Překročený rozpočet: {exceeded} · nedoložená spotřeba: {unknown}</p>
        </>}
        {model.busy && !model.items.length && <p role="status">Načítám pozorování…</p>}
        {!model.busy && !model.items.length && model.observerConfigured && <p>Zatím bez pozorování běhů.</p>}
        {!!rows.length && <ul className="execution-observations__list">{rows.map(item => {
          const title = compactTitle(item, cards);
          const usage = item.observation?.cumulative;
          const row = <><strong>{title}</strong><span>{observationStatus(item)} · {item.intent.executionId.slice(0, 8)} · {hasProviderUsage(item) && usage ? `${formatUsdCents(usage.listCostCents)} podle ceníku` : "Spotřeba nedoložena"}</span>
            {item.listBudgetExceeded && <strong className="execution-observations__warning">Překročen ceníkový rozpočet</strong>}</>;
          return <li key={item.intent.id}>{onSelect
            ? <button type="button" aria-label={`Pozorování běhu ${title}`} onClick={() => onSelect(item.intent.executionId, item.intent.id)}>{row}</button>
            : <div className="execution-observations__row">{row}</div>}</li>;
        })}</ul>}
        {onViewAll && <button className="execution-observations__all" type="button" onClick={onViewAll}>Všechny záznamy ({model.items.length})</button>}
      </>}
  </section>;
}
export default function ExecutionObservations({ model, selectedExecutionId, selectedIntentId, onSelect, compact = false, cards = [], onViewAll }: {
  model: ExecutionObservationsView; selectedExecutionId?: string; selectedIntentId?: string; onSelect?: (executionId: string, intentId: string) => void;
  compact?: boolean; cards?: { id: string; name: string }[]; onViewAll?: () => void;
}) {
  if (compact) return <Compact model={model} cards={cards} onSelect={onSelect} onViewAll={onViewAll} />;
  const selected = selectedExecutionId ? model.items.find(item => item.intent.executionId === selectedExecutionId && (!selectedIntentId || item.intent.id === selectedIntentId)) ?? null : null;
  const shown = model.items.slice(0, 6);
  if (selected && !shown.some(item => item.intent.executionId === selected.intent.executionId)) shown.push(selected);
  return <section className="execution-observations" aria-label="Pozorování izolovaných běhů" aria-busy={model.busy}>
    <header className="execution-observations__head"><div><h2>Pozorování běhů a spotřeby</h2><p>Záznamy z API poskytovatele doložené brokerem.</p></div>
      <button type="button" onClick={model.refresh} disabled={model.busy}>Obnovit pozorování</button></header>
    <p>Projekt <code>{model.project || "není vybrán"}</code> · prostor <code>{model.workspace || "není vybrán"}</code>. Zobrazuje se nejvýše 100 posledních běhů.</p>
    {!model.busy && !model.error && !model.observerConfigured && <p className="execution-observations__notice">Broker pozorování není v tomto prostoru nakonfigurován.</p>}
    {!model.busy && !model.error && model.observerConfigured && !model.providerAccessVerified && <p className="execution-observations__notice">Konfigurace pozorovatele existuje; přístup k poskytovateli nebyl tímto čtením ověřen.</p>}
    {model.busy && <p role="status">Načítám pozorování…</p>}
    {model.error && <p className="execution-observations__warning" role="alert">Pozorování nejsou dostupná: {model.error}</p>}
    {!model.busy && !model.error && !model.items.length && <p>Zatím nejsou uložena žádná pozorování běhů.</p>}
    {!!model.items.length && <ul className="execution-observations__list">{shown.map(item => <li key={item.intent.id}>
      {onSelect ? <button type="button" aria-pressed={selected?.intent.id === item.intent.id} onClick={() => onSelect(item.intent.executionId, item.intent.id)}><Summary item={item} /></button>
        : <div className="execution-observations__row"><Summary item={item} /></div>}
    </li>)}</ul>}
    {selectedExecutionId && !selected && !model.busy && !model.error && <p role="status">Vybraný běh není v tomto rozsahu načtených pozorování; nebyl nahrazen jiným.</p>}
    {selected && <section className="execution-observations__detail" aria-label="Přesné pozorování vybraného běhu">
      <h3>{observationStatus(selected)}</h3>
      <dl className="execution-observations__identity">
        <dt>Neměnný záznam záměru</dt><dd><code>{selected.intent.id}</code></dd>
        <dt>Karta</dt><dd><code>{selected.intent.nodeId}</code></dd>
        <dt>Běh a epocha</dt><dd><code>{selected.intent.executionId}</code> · {selected.intent.epoch}</dd>
        <dt>Přijatá revize</dt><dd><code>{selected.intent.acceptedRevision}</code></dd>
        <dt>Repozitář a commit</dt><dd>{selected.intent.repository.url} · <code>{selected.intent.repository.commitSha}</code></dd>
        <dt>Agent a prostředí</dt><dd>{selected.intent.agentId} v{selected.intent.agentVersion} · {selected.intent.environmentId}</dd>
        <dt>Zdroj a čas pozorování</dt><dd>{selected.observation ? selected.observation.source + " · " + observedAt(selected.observation.observedAt) : "Zatím bez čtení od brokera"}</dd>
        <dt>Čas načtení do Canvasu</dt><dd>{model.loadedAt === null ? "Načtení není dokončeno" : new Date(model.loadedAt).toLocaleString("cs-CZ")}</dd>
      </dl>
      <Usage item={selected} />
      {selected.listBudgetExceeded && <p className="execution-observations__warning">Poslední zaznamenaná cena podle ceníku poskytovatele překročila uložený rozpočet. Tento údaj sám běh nezastavuje ani nemění oprávnění.</p>}
      <p>Rozpočet podle ceníku: {formatUsdCents(selected.intent.maxListCostCents)} · {hasProviderUsage(selected) ? selected.listBudgetExceeded ? "překročen podle posledního čtení brokera" : "nepřekročen podle posledního čtení brokera" : "stav neznámý bez doloženého čtení session"}.</p>
      <p>Údaje o spotřebě jsou kumulativní čtení brokera z API poskytovatele, nikoli faktura. Pozorování neobnovuje oprávnění; stav „nečinný“ nepotvrzuje ukončení. Ukončení je potvrzeno pouze při výslovném stavu „terminated“.</p>
    </section>}
    <footer className="execution-observations__foot">Přístup poskytovatele není ověřen samotnou konfigurací. Ceníková spotřeba není faktura ani tvrdý finanční limit.</footer>
  </section>;
}
