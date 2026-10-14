// K upřesnění: otevřené otázky k zadání (fragment druhu question) pro člověka nebo agenta. Odpověď se
// uloží k otázce (otázku pro člověka zodpoví jen člověk); z otázky jde rovnou zadat výzkum.
import { useState } from "react";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { useFragmentDetail } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import { questionItems, type Flat } from "../logic/vault-dock-model";
import { vaultOp, type VaultScope } from "../logic/vault-actions";

function QuestionCard({ scope, item, readOnly }: { scope: VaultScope; item: Flat; readOnly: boolean }) {
  const { node, parent } = item;
  const { detail } = useFragmentDetail(scope.project, scope.workspace, node.id, null, node);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const asked = detail?.details?.question;
  async function act(body: Record<string, unknown>, done: string) {
    setBusy(true); setMessage("");
    try { await vaultOp(scope, body); setMessage(done); setAnswer(""); }
    catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return (
    <section className="vault-panel" aria-label={"Otázka " + node.title}>
      <div className="vault-actions">
        <span className="vault-research-card__where">{parent?.title ?? ""}</span>
        <strong className="vault-mvp__title">{node.title}</strong>
        <span className="vault-pill">pro: {(asked?.askedFor ?? node.question?.askedFor) === "agent" ? "agenta" : "člověka"}</span>
      </div>
      {detail?.fragment.text && <p className="vault-panel__text">{detail.fragment.text}</p>}
      {asked?.proposal && <p className="vault-panel__text">Návrh agenta: {asked.proposal}</p>}
      {asked?.answer ? <p className="vault-panel__text"><strong>Odpověď:</strong> {asked.answer} <span className="vault-row__side">({asked.answeredBy})</span></p>
        : !readOnly && (
          <>
            <label className="vault-field">Odpověď
              <textarea rows={2} value={answer} maxLength={8000} onChange={(event) => setAnswer(event.target.value)} />
            </label>
            <div className="vault-actions">
              <button type="button" className="vault-button vault-button--primary" disabled={busy || !answer.trim() || !detail}
                onClick={() => void act({ op: "answer", fragmentId: node.id, expectedRevision: detail!.latestRevision, answer }, "Odpověď uložena.")}>Odpovědět</button>
              <button type="button" className="vault-button" disabled={busy || !parent}
                onClick={() => void act({ op: "research", fragmentId: parent!.id, title: node.title.slice(0, 160), question: node.title, text: "" },
                  "Výzkum zadán; najdeš ho v sekci Výzkum.")}>Zadat výzkum</button>
            </div>
          </>
        )}
      {message && <p className="vault-dock__notice" role="status">{message}</p>}
    </section>
  );
}

export default function QuestionsSection({ scope, roots, query, readOnly }: { scope: VaultScope; roots: VaultNode[]; query: string; readOnly: boolean }) {
  const items = questionItems(roots, query).sort((a, b) => Number(!!a.node.question?.answered) - Number(!!b.node.question?.answered));
  return (
    <div className="vault-stack" data-testid="vault-questions">
      <p className="vault-dock__lead">Otázky, bez kterých nejde zadání dotáhnout. Odpověď se uloží k otázce a promítne se do další revize fragmentu nebo z ní vznikne výzkum.</p>
      {items.length ? items.map((item) => <QuestionCard key={item.node.id} scope={scope} item={item} readOnly={readOnly} />)
        : <div className="vault-dock__empty">{query ? "Hledání nenašlo žádnou otázku." : "Žádné otázky k upřesnění. Položíš je v sekci Zadání u kapitoly („Položit otázku“); agent je klade přes op question."}</div>}
    </div>
  );
}
