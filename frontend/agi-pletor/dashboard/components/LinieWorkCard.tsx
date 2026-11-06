import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { acceptanceLabel, canAccept, diffSentence, diffView, roleLabel, shortSha, type DiffView, type LinieLane } from "../logic/linie-view";
import LiniePreview, { type LinieAct } from "./LiniePreview";

type Props = { lane: LinieLane | null; project: string; onAct: LinieAct };

/**
 * Karta PRACOVNÍ VĚTEV: kdo co dělá, náhled, co by přešlo do rodiče (`GET /diff`) a přijetí hlavy s poznámkou.
 * Zápis hlásí rodič přes `onAct`, který stav znovu načte.
 */
export default function LinieWorkCard({ lane, project, onAct }: Props) {
  const target = lane?.parent ?? "";
  const [diff, setDiff] = useState<DiffView | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => {
    setDiff(null);
    setError("");
    if (!lane || !target) return;
    let live = true;
    api<unknown>(`/api/pletor/linie/diff?${new URLSearchParams({ branch: lane.name, target })}`).then(
      (raw) => { if (live) setDiff(diffView(raw)); },
      (failure: unknown) => { if (live) setError(failure instanceof Error ? failure.message : "Rozdíl se nenačetl."); },
    );
    return () => { live = false; };
  }, [lane?.name, lane?.sha, target]);

  if (!lane) return (
    <section className="pletor-dashboard__linie-card pletor-dashboard__linie-card--work" aria-label="Pracovní větev">
      <h2 className="pletor-dashboard__linie-card-title">Pracovní větev</h2>
      <p className="pletor-dashboard__note">Žádná pracovní větev novější než main. Novou založ z develop.</p>
    </section>
  );

  const accept = () => onAct(api("/api/pletor/linie/accept", { branch: lane.name, sha: lane.sha, target, note }), `Přijato ${shortSha(lane.sha)} do ${target}.`);
  const revoke = () => onAct(api(`/api/pletor/linie/accept/${encodeURIComponent(lane.name)}`, {}, "DELETE"), `Přijetí ${lane.name} zrušeno.`);

  return (
    <section className="pletor-dashboard__linie-card pletor-dashboard__linie-card--work" aria-label="Pracovní větev">
      <h2 className="pletor-dashboard__linie-card-title">Pracovní větev</h2>
      <p className="pletor-dashboard__mono">{lane.name} ({roleLabel(lane.role)}) @ {shortSha(lane.sha)}</p>
      <ul className="pletor-dashboard__linie-points">
        <li><strong>Claude:</strong> vytváří a testuje.</li>
        <li><strong>Ty:</strong> zkoušíš náhled a koriguješ.</li>
      </ul>
      <LiniePreview lane={lane} project={project} onAct={onAct} />
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      {target && !diff && !error && <p className="pletor-dashboard__note" role="status">Načítám rozdíl…</p>}
      {diff && (
        <details>
          <summary>{diffSentence(target, diff)}</summary>
          {diff.stat && <pre className="pletor-dashboard__pre">{diff.stat}</pre>}
        </details>
      )}
      <span className="pletor-dashboard__tag">{acceptanceLabel(lane)}</span>
      {canAccept(lane) && (
        <>
          <input className="pletor-dashboard__input" aria-label="Poznámka k přijetí" placeholder="poznámka" value={note} onChange={(event) => setNote(event.target.value)} />
          <span className="pletor-dashboard__tools">
            <button type="button" className="pletor-dashboard__button" onClick={accept}>Přijmout hlavu {shortSha(lane.sha)} do {target}</button>
            {lane.acceptance && <button type="button" className="pletor-dashboard__button" onClick={revoke}>Zrušit přijetí</button>}
          </span>
        </>
      )}
      {lane.pr?.url && <a href={lane.pr.url} target="_blank" rel="noreferrer">PR #{lane.pr.number} ({lane.pr.state}) ↗</a>}
    </section>
  );
}
