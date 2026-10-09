// Kola karty: přepínač kol (v1 ✓ · v2 ●), Historie kol jen ke čtení a tlačítko „Otevřít v2 podle nového zadání“.
// Otevření kola potvrzuje člověk: dílek nic neukládá sám, žádost bublá přes onOpenRound a zapisuje rodič (App)
// přes POST /api/desktop-v3/card-round. Historii čte GET /api/desktop-v3/card-rounds.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import {
  openRoundLabel,
  roundChips,
  roundDigest,
  roundOffer,
  type RoundRecord,
  type RoundsResponse,
} from "@/editor/node-detail/rounds/logic/rounds-model";
import "@/editor/node-detail/rounds/styles/rounds.css";

/** Přepínač kol; minulé kolo otevře Historii kol, aktuální vrátí k práci. */
export function RoundSwitch({ current, closed, selected, onSelect }: {
  current: number;
  closed: boolean;
  selected?: number;
  onSelect?: (round: number) => void;
}) {
  if (current < 2) return null;
  return (
    <span className="rounds-switch" role="group" aria-label="Kola karty" data-testid="round-switch">
      {roundChips(current, closed).map((chip, index) => (
        <span key={chip.round} className="rounds-switch__item">
          {index > 0 && <span className="rounds-switch__sep" aria-hidden="true">·</span>}
          <button type="button" disabled={!onSelect}
            className={"rounds-switch__chip" + (chip.current ? " rounds-switch__chip--current" : "") + (selected === chip.round ? " rounds-switch__chip--selected" : "")}
            aria-pressed={selected === chip.round}
            title={chip.current ? (closed ? "Aktuální kolo je uzavřené" : "Aktuální kolo: práce běží") : "Uzavřené kolo: historie jen ke čtení"}
            onClick={() => onSelect?.(chip.round)}>
            {chip.label} {chip.mark}
          </button>
        </span>
      ))}
    </span>
  );
}

/** Nabídka nového kola: výrazná při ⚠ změně fragmentu, jinak tichá ruční volba. Jen pro člověka v UI. */
export function OpenRoundOffer({ current, closed, readOnly, busy, briefChanged, onOpenRound }: {
  current: number;
  closed: boolean;
  readOnly: boolean;
  busy: boolean;
  briefChanged: number;
  onOpenRound: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const offer = roundOffer(closed, readOnly, briefChanged);
  if (!offer) return null;
  async function submit() {
    setSending(true);
    setError("");
    try {
      await onOpenRound(reason.trim() || (briefChanged ? "Změna zadání ve schránce" : "Vylepšení karty"));
      setReason("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSending(false);
    }
  }
  return (
    <div className={"rounds-offer rounds-offer--" + offer} data-testid="round-offer">
      {offer === "prominent" && (
        <p className="rounds-offer__why">⚠ Zadání ve schránce se po uzavření změnilo ({briefChanged}). Vylepšení začne v čisté kartě v{current + 1}; v{current} zůstane v Historii kol.</p>
      )}
      <label className="rounds-offer__field">
        Proč nové kolo
        <input aria-label="Důvod nového kola" maxLength={2000} value={reason} disabled={busy || sending}
          placeholder={briefChanged ? "Změna zadání ve schránce" : "Co se má vylepšit"} onChange={(e) => setReason(e.target.value)} />
      </label>
      <button type="button" className={offer === "prominent" ? "primary" : ""} data-testid="round-open" disabled={busy || sending}
        title={`Zamrazí v${current} do historie (pipeline, důkazy, nálezy, commity) a otevře čistou v${current + 1}. Potvrzuje člověk.`}
        onClick={() => void submit()}>
        {openRoundLabel(current)}
      </button>
      {error && <p className="rounds-offer__error" role="alert">{error}</p>}
    </div>
  );
}

/** Jedno zamrazené kolo jen ke čtení: postup, chyby, nálezy, commity, Podněty, zadání kola. */
export function RoundRecordView({ record }: { record: RoundRecord }) {
  const digest = roundDigest(record);
  return (
    <article className="rounds-record" data-testid="round-record">
      <header className="rounds-record__head">
        <b>v{record.round}</b> · uzavřeno {record.closedAt || "—"} · zamrazeno {record.frozenAt}
        {record.openReason && <span className="rounds-record__reason"> · důvod kola: {record.openReason}</span>}
      </header>
      <ul className="rounds-record__facts" aria-label="Výtah kola">
        <li title="Etapy pipeline, které prošly">pipeline {digest.stagesPassed}/{digest.stages.length}</li>
        <li title="Splněné bloky">bloky {digest.blocksMet}/{digest.blocks}</li>
        {digest.evidence.map((item) => <li key={item.key} className={"rounds-record__proof--" + item.status}>{item.key}: {item.status}</li>)}
        <li title="Chyby: selhané etapy, chyby v předávkách a v paměti agenta">chyby {digest.errorCount}</li>
        <li title="Podněty: otevřené přešly do dalšího kola">💡 {digest.ideasOpen} otevř. · {digest.ideasDone} hotových</li>
      </ul>
      {record.done?.note && <p className="rounds-record__note">{record.done.note}</p>}
      <details open>
        <summary>Postup (pipeline s předávkami)</summary>
        <ol className="rounds-record__list">
          {digest.stages.map((stage, index) => (
            <li key={stage.id ?? index}><span aria-hidden="true">{stage.ok ? "✓" : "✗"}</span> <b>{stage.title}</b>
              {stage.doneBy && <span className="rounds-record__meta"> · {stage.doneBy}</span>}
              {stage.note && <p className="rounds-record__text">{stage.note}</p>}</li>
          ))}
          {!digest.stages.length && <li className="muted">Kolo nemělo pipeline.</li>}
        </ol>
      </details>
      {!!digest.findings.length && (
        <details>
          <summary>Nálezy review a kritiků ({digest.findings.length})</summary>
          <ul className="rounds-record__list">
            {digest.findings.map((item, index) => <li key={item.id ?? index}><b>{item.title}</b> ({item.status}){item.note && <p className="rounds-record__text">{item.note}</p>}</li>)}
          </ul>
        </details>
      )}
      {digest.errorCount > 0 && (
        <details>
          <summary>Chyby a opravy</summary>
          <ul className="rounds-record__list">
            {digest.errors.failedStages.map((item, index) => <li key={"s" + index}><b>{item.title}</b>: {item.note}</li>)}
            {digest.errors.handoffErrors.map((item) => <li key={item.edgeId}>Předávka: {item.errors}</li>)}
            {digest.errors.agentFailures.trim() && <li>Paměť agenta: {digest.errors.agentFailures}</li>}
            {digest.errors.agentFixes.trim() && <li>Opravy: {digest.errors.agentFixes}</li>}
          </ul>
        </details>
      )}
      {!!digest.decided.length && (
        <details>
          <summary>Rozhodnutí v{record.round} ({digest.decided.length})</summary>
          <p className="rounds-record__meta">Další kolo je nepřebírá: nové zadání rozhoduje porty a kritéria znovu.</p>
          <ul className="rounds-record__list">
            {digest.decided.map((item, index) => (
              <li key={item.kind + index}><span aria-hidden="true">{item.kind === "port" ? "⇢" : item.kind === "criterion" ? "☑" : "◆"}</span> {item.text}</li>
            ))}
          </ul>
        </details>
      )}
      <details>
        <summary>Commity a soubory</summary>
        <p className="rounds-record__text">
          {digest.commit ? <>commit <code>{digest.commit}</code> </> : "commit nezapsán "}
          {digest.prUrl && <a href={digest.prUrl} target="_blank" rel="noreferrer">PR / merge</a>}
        </p>
        {!!digest.touched.length && <ul className="rounds-record__files">{digest.touched.map((path) => <li key={path}><code>{path}</code></li>)}</ul>}
      </details>
      <details>
        <summary>Doslovné zadání kola</summary>
        {record.brief.fragments.map((item) => (
          <div key={item.fragmentId} className="rounds-record__fragment">
            <b>{item.title ?? item.fragmentId}</b> <span className="rounds-record__meta">rev. {item.revision}</span>
            <pre className="rounds-record__pre">{item.available ? item.text : "Revize fragmentu není dostupná."}</pre>
          </div>
        ))}
        {record.brief.goal?.goal && <p className="rounds-record__text"><b>Cíl:</b> {record.brief.goal.goal}</p>}
      </details>
      {!!digest.results.length && (
        <details>
          <summary>Výsledky agentů ({digest.results.length})</summary>
          <ul className="rounds-record__list">
            {digest.results.map((item) => <li key={item.id}><code>{item.id.slice(0, 8)}</code> {item.agent} · {item.createdAt}{item.doneProposed ? " · navrhl uzavření" : ""}</li>)}
          </ul>
        </details>
      )}
    </article>
  );
}

/** Záložka Historie kol: přepínač, vybrané kolo jen ke čtení a nabídka nového kola. */
export default function RoundsPanel({ project, workspace, nodeId, current, closed, readOnly, busy, briefChanged, revision, selected, onSelect, onOpenRound }: {
  project: string;
  workspace: string;
  nodeId: string;
  current: number;
  closed: boolean;
  readOnly: boolean;
  busy: boolean;
  briefChanged: number;
  /** Otisk stavu plátna: změna znovu načte historii. */
  revision: unknown;
  selected: number;
  onSelect: (round: number) => void;
  onOpenRound?: (reason: string) => Promise<void>;
}) {
  const [data, setData] = useState<RoundsResponse | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    api<RoundsResponse>("/api/desktop-v3/card-rounds?" + new URLSearchParams({ project, workspace, nodeId }))
      .then((value) => { if (alive) { setData(value); setError(""); } })
      .catch((err: unknown) => { if (alive) setError(err instanceof Error ? err.message : String(err)); });
    return () => { alive = false; };
  }, [project, workspace, nodeId, revision, current]);
  const record = data?.rounds.find((item) => item.round === selected);
  return (
    <div className="rounds" data-testid="rounds-panel">
      <RoundSwitch current={current} closed={closed} selected={selected} onSelect={onSelect} />
      {onOpenRound && <OpenRoundOffer current={current} closed={closed} readOnly={readOnly} busy={busy} briefChanged={briefChanged} onOpenRound={onOpenRound} />}
      {error && <p className="rounds__error" role="alert">{error}</p>}
      {record ? <RoundRecordView record={record} /> : (
        <p className="muted" data-testid="rounds-current">
          {current < 2
            ? "Karta je v prvním kole. Až ji člověk uzavře a zadání se změní, otevře v2: v1 se zamrazí sem jen ke čtení."
            : `Aktuální kolo v${current}${closed ? " je uzavřené" : " běží"}: zadání a práce jsou v záložkách Zadání a Práce. Minulá kola vyberte v přepínači.`}
        </p>
      )}
    </div>
  );
}
