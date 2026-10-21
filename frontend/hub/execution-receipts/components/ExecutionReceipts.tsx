import type { ExecutionReceiptsView } from "../logic/use-execution-receipts";
import { executionLabel, receiptDetails, unixTime } from "../logic/execution-receipts";
import "../styles/execution-receipts.css";

export default function ExecutionReceipts({ model }: { model: ExecutionReceiptsView }) {
  const selected = model.selected;
  const stale = !!selected && !!model.context?.acceptedHead && selected.acceptedRevision !== model.context.acceptedHead;
  const cardName = (id: string) => model.choices.find(node => node.id === id)?.name ?? "Odstraněná nebo nedostupná karta";
  return <section className="execution-receipts" aria-label="Běhy agentů a nahlášené výsledky" aria-busy={model.busy}>
    <header className="execution-receipts__head"><div><h2>Běhy agentů a nahlášené výsledky</h2>
      <p>Nahlášený výsledek není nezávislé ověření ani dokončení karty.</p></div>
      <button type="button" onClick={model.refresh} disabled={model.busy}>Obnovit běhy a výsledky</button>
    </header>
    <>
      <label className="execution-receipts__field">Karta pro historii běhů
        <select aria-label="Karta pro historii běhů" value={model.nodeId} onChange={event => model.selectCard(event.target.value)}>
          <option value="">Všechny karty včetně odstraněných</option>
          {model.choices.map(node => <option key={node.id} value={node.id}>{node.name}</option>)}
        </select>
      </label>
      <p>Projekt <code>{model.project}</code> · prostor <code>{model.workspace}</code>. Nejvýše 100 posledních běhů {model.nodeId ? "vybrané karty" : "všech karet v tomto prostoru"}.</p>
      {!model.nodeId && <p>Historické výsledky patří původní přijaté revizi každého běhu. Nepotvrzují aktuální zadání ani jeho nezávislé ověření.</p>}
      {model.context && !model.context.available && <p className="execution-receipts__warning">Nové vykonávání není dostupné: {model.context.unavailableReason}. Historie zůstává podkladem k původnímu zadání.</p>}
      {model.busy && <p role="status">Načítám běhy…</p>}
      {model.error && <p className="execution-receipts__warning" role="alert">{model.error} Obnovte historii pro další pokus.</p>}
      {model.missingSelection && <p role="alert">Vybraný běh již není v načtené historii. Nebyl nahrazen jiným během.</p>}
      {!model.busy && !model.error && !model.executions.length && <p>Zatím žádné běhy v tomto výběru.</p>}
      <ul className="execution-receipts__list">{model.executions.map(item => <li key={item.executionId}>
        <button type="button" onClick={() => model.selectExecution(item.executionId)} aria-pressed={selected?.executionId === item.executionId}>
          Epocha {item.epoch} · {executionLabel(item)}
        </button><span>{cardName(item.nodeId)} · <code>{item.nodeId}</code></span><span>{item.createdAt ? new Date(item.createdAt).toLocaleString("cs-CZ") : "Čas založení není dostupný"}</span>
      </li>)}</ul>
    </>
    {selected && <section className="execution-receipts__details" aria-label="Podrobnosti běhu">
      <h3>{executionLabel(selected)} · epocha {selected.epoch}</h3>
      <p>Uložený vlastník: {selected.owner ?? "Není doložen"}.</p>
      {stale && <p className="execution-receipts__warning">Běh patří starší přijaté revizi. Výsledek nepotvrzuje aktuální zadání.</p>}
      <dl className="execution-receipts__identity">
        <dt>Běh</dt><dd><code>{selected.executionId}</code></dd>
        <dt>Karta</dt><dd>{cardName(selected.nodeId)} · <code>{selected.nodeId}</code></dd>
        <dt>Přijatá revize</dt><dd><code>{selected.acceptedRevision}</code></dd>
        <dt>Otisk zadání</dt><dd><code>{selected.assignmentDigest}</code></dd>
        <dt>Platnost rezervace do</dt><dd>{unixTime(selected.expiresAt)}</dd>
        <dt>Stav načten ze serveru</dt><dd>{unixTime(selected.serverNow)}</dd>
      </dl><p>Stav platí k poslednímu načtení. Běhy spouští Agent Office; historie se neobnovuje automaticky.</p>
      {selected.budget ? <p>Protokol v2 · pokus {selected.budget.attempt} · oprava {selected.budget.repairRound} · {selected.budget.kind}. Nejvýše {selected.budget.maxRunSeconds} sekund oprávnění, pevný konec {unixTime(selected.budget.runDeadlineAt)}. Změna pravidel tento konec neposouvá.</p> : <p>Starší protokol v1 · pevný časový limit běhu není doložen.</p>}
      {model.canCancel && !model.cancellation && <button type="button" onClick={model.prepareCancel}>Zkontrolovat zrušení oprávnění</button>}
      {model.cancellation && <section className="execution-receipts__warning" aria-label="Potvrzení zrušení oprávnění">
        <h4>Zrušit tento konkrétní běh?</h4><p>Běh <code>{model.cancellation.executionId}</code> · epocha {model.cancellation.payload.epoch}. Spotřebovaný pokus se nevrací. Nahlášený výsledek zůstává uložen. Odebrání oprávnění není důkaz zastavení všech procesů.</p>
        <label><input type="checkbox" checked={model.cancelAck} disabled={model.cancelling} onChange={event => model.acknowledgeCancel(event.target.checked)} /> Potvrzuji zrušení oprávnění tohoto běhu a epochy.</label>
        <button type="button" disabled={!model.cancelAck || model.cancelling} onClick={model.confirmCancel}>Potvrdit zrušení oprávnění</button><button type="button" disabled={model.cancelling} onClick={model.dismissCancel}>Zpět</button>
      </section>}
      {model.detailBusy && <p role="status">Načítám nahlášené výsledky…</p>}
      {model.detailError && <p className="execution-receipts__warning" role="alert">Výsledky se nepodařilo načíst: {model.detailError}</p>}
      {!model.detailBusy && !model.detailError && !model.receipts.length && <p>Tento běh zatím nemá nahlášený výsledek.</p>}
      {model.receipts.map(receipt => <article className="execution-receipts__receipt" key={receipt.receiptId}>
        <h4>Výsledek nahlášen · {new Date(receipt.createdAt).toLocaleString("cs-CZ")}</h4>
        <p>Potvrzení příjmu <code>{receipt.receiptId}</code>. Obsah deklaruje agent; jeho správnost nebyla nezávisle ověřena.</p>
        <pre>{receipt.result.summary}</pre>
        {receiptDetails(receipt) && <details><summary>Další nahlášené podklady</summary><pre>{receiptDetails(receipt)}</pre></details>}
      </article>)}
    </section>}
  </section>;
}
