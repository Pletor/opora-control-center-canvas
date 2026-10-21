import type { FormalVerificationView } from "../logic/use-formal-verification";
import { formalOutcome } from "../logic/formal-verification";
import FormalDetail from "./FormalDetail";
import "../styles/formal-verification.css";
export default function FormalVerification({ model, currentAcceptedHead }: { model: FormalVerificationView; currentAcceptedHead: string | null }) {
  return <section className="formal-verification" aria-label="Formální podklady">
    <header className="formal-verification__header"><div><h2>Formální podklady</h2><p>Požadavky a výsledky pro tento pracovní prostor · nejvýše 100 posledních.</p></div>
      <button type="button" onClick={model.refresh}>Obnovit historii a vybraný podklad</button></header>
    <p className="formal-verification__trust">Pouze čtení. Všechny podklady jsou nahlášené agentem; ani výsledek „prošlo“ nemá důvěru nezávislého ověřovače.</p>
    {model.busy && <p role="status">Načítám historii formálních podkladů…</p>}
    {model.error && <p className="formal-verification__warning" role="alert">{model.error}</p>}
    {!model.busy && !model.error && !model.requests.length && <p>V tomto prostoru zatím nejsou formální požadavky. Agent je může odevzdat pomocí execution API.</p>}
    <div className="formal-verification__list" aria-label="Historie formálních požadavků">{model.requests.map(record => <button type="button" key={record.id}
      className={record.id === model.selectedId ? "formal-verification__row formal-verification__row--selected" : "formal-verification__row"}
      aria-pressed={record.id === model.selectedId} onClick={() => model.select(record.id)}>
      <strong>{record.verification.tool.name.toUpperCase()} · karta {record.nodeId}</strong><span>{formalOutcome(record)}</span>
      <code>{record.id}</code><small>{new Date(record.createdAt).toLocaleString("cs-CZ")}</small>
    </button>)}</div>
    {!model.selectedId && <p>Vyberte přesný požadavek pro zobrazení tvrzení, předpokladů, konfigurace a souborů.</p>}
    {model.selectedId && <p>Vybraný požadavek: <code>{model.selectedId}</code></p>}
    {model.detailBusy && <p role="status">Načítám přesný vybraný požadavek…</p>}
    {model.detailError && <p className="formal-verification__warning" role="alert">Vybraný podklad není dostupný. Nebyl nahrazen jiným požadavkem. {model.detailError}</p>}
    {model.missingSelection && <p>Vybraný požadavek nebyl nalezen. Vyberte jiný požadavek výslovně.</p>}
    {model.selected?.id === model.selectedId && <FormalDetail record={model.selected} currentAcceptedHead={currentAcceptedHead} />}
  </section>;
}
