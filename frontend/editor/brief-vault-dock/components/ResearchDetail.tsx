// Detail výzkumu: otázka, verdikt s jistotou a kolem, doporučený postup, důkazy s odkazy, zpětná vazba
// člověka a akce (další kolo, povýšit do zadání, co dostane agent). Odkaz důkazu jen http(s).
import { useState } from "react";
import type { Feedback } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { useFragmentDetail } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import { CONFIDENCE, RESEARCH_STATUS, VERDICTS, hostOf, safeHref, shortWhen, type Flat } from "../logic/vault-dock-model";
import { researchBriefUrl, useVaultGet, vaultOp, type VaultScope } from "../logic/vault-actions";
import FeedbackBox, { FeedbackList } from "./FeedbackBox";
import PromoteForm from "./PromoteForm";

export default function ResearchDetail({ scope, item, readOnly }: { scope: VaultScope; item: Flat; readOnly: boolean }) {
  const { node, parent } = item;
  const { detail, error } = useFragmentDetail(scope.project, scope.workspace, node.id, null, node);
  const [showPackage, setShowPackage] = useState(false);
  const [promote, setPromote] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const pack = useVaultGet<Record<string, unknown>>(showPackage ? researchBriefUrl(scope, node.id) : null, node);
  if (error) return <p className="vault-dock__error" role="alert">Výzkum nelze načíst: {error}</p>;
  if (!detail) return <p className="vault-dock__notice" role="status">Načítám výzkum…</p>;
  const research = detail.details?.research;
  const verdict = VERDICTS[research?.verdict ?? "unverified"];
  const feedback: Feedback[] = detail.feedback ?? [];
  const last = detail.history[detail.history.length - 1];
  async function act(run: () => Promise<unknown>, done: string) {
    setBusy(true); setMessage("");
    try { await run(); setMessage(done); } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  const nextRound = () => act(() => vaultOp(scope, { op: "research-update", fragmentId: node.id, expectedRevision: detail.latestRevision,
    status: "assigned", round: (research?.round ?? 1) + 1, note: "Další kolo výzkumu podle zpětné vazby." }), "Další kolo je zadané; agent ho najde v balíčku research-brief.");
  return (
    <section className="vault-panel" aria-label={"Výzkum " + node.title} data-testid="vault-research-detail">
      <div>
        <div className="vault-eyebrow">Otázka · {parent?.title ?? "fragment"}</div>
        <p className="vault-question">{research?.question || node.title}</p>
      </div>
      <div className="vault-actions">
        <span className={"vault-pill vault-verdict vault-verdict--" + verdict.tone}><span className="vault-verdict__dot" aria-hidden="true" />{verdict.label}</span>
        <span className="vault-pill">jistota: {CONFIDENCE[research?.confidence ?? ""]}</span>
        <span className="vault-pill">kolo {research?.round ?? 1} · {RESEARCH_STATUS[research?.status ?? "assigned"]}</span>
      </div>
      <div>
        <h4 className="vault-panel__title">Doporučený postup</h4>
        <p className="vault-panel__text">{research?.approach || "Zatím bez postupu: výzkum ještě nemá výsledek."}</p>
      </div>
      {node.chars > 0 && detail.fragment.text && <p className="vault-panel__text">{detail.fragment.text}</p>}
      <div>
        <h4 className="vault-panel__title">Důkazy</h4>
        {research?.evidence.length ? research.evidence.map((entry, index) => {
          const href = safeHref(entry.url);
          return (
            <div key={index} className="vault-evidence">
              {href ? <a href={href} target="_blank" rel="noopener noreferrer">{entry.title}</a> : <span>{entry.title}</span>}
              {entry.quote && <span className="vault-evidence__quote">„{entry.quote}“</span>}
              <span className="vault-evidence__source">{hostOf(entry.url) || entry.url} · ověřeno {entry.accessedAt}</span>
            </div>
          );
        }) : <p className="vault-panel__text">Žádný důkaz. Bez důkazu s URL zůstává verdikt „neověřeno“.</p>}
      </div>
      <FeedbackList items={feedback} />
      {!readOnly && <FeedbackBox scope={scope} fragmentId={node.id} />}
      {!readOnly && (
        <div className="vault-actions">
          <button type="button" className="vault-button vault-button--primary" disabled={busy} onClick={() => void nextRound()}>Zadat další kolo výzkumu</button>
          <button type="button" className="vault-button" disabled={busy || !parent} aria-expanded={promote} onClick={() => setPromote((value) => !value)}>Povýšit do zadání</button>
          <button type="button" className="vault-button" aria-expanded={showPackage} onClick={() => setShowPackage((value) => !value)}>Co dostane agent</button>
        </div>
      )}
      {message && <p className="vault-dock__notice" role="status">{message}</p>}
      {promote && parent && (
        <PromoteForm scope={scope} researchId={node.id} parentId={parent.id} approach={research?.approach ?? ""}
          onDone={(text) => { setPromote(false); setMessage(text); }} />
      )}
      {showPackage && (
        <div className="vault-package" data-testid="vault-package">
          <b>Balíček pro agenta (jen data, ne pokyny):</b> cíl plánu · cesta · doslovný text kapitoly · dosavadní výzkum a důkazy ·
          zpětná vazba · otevřené otázky · rozhodnutí plátna. Agent hledá na internetu a vrátí verdikt, důkazy a postup
          (<code>op: research-update</code>). Stažení: <code>GET /api/brief-vault/research-brief?fragment={node.id}</code>.
          {pack.error && <p className="vault-dock__error" role="alert">{pack.error}</p>}
          {pack.data && <pre>{JSON.stringify(pack.data, null, 2)}</pre>}
        </div>
      )}
      {last && <p className="vault-research-card__meta">r{last.revision} · {last.by} · {shortWhen(last.at)} — {last.note}</p>}
    </section>
  );
}
