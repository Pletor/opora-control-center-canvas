import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { canAccept, diffSentence, diffView, shortSha, targetOf, type DiffView, type LinieBranch } from "../logic/linie-view";

type Props = { branch: LinieBranch; onAct: (write: Promise<unknown>, done: string) => void };

/** Detail vybrané větve: co by přešlo do rodiče (`GET /diff`) a přijetí hlavy s poznámkou, nebo jeho zrušení. Zápis hlásí rodič. */
export default function LinieBranchDetail({ branch, onAct }: Props) {
  const target = targetOf(branch);
  const [diff, setDiff] = useState<DiffView | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => {
    setDiff(null);
    setError("");
    if (!target) return;
    let live = true;
    api<unknown>(`/api/pletor/linie/diff?${new URLSearchParams({ branch: branch.name, target })}`).then(
      (raw) => { if (live) setDiff(diffView(raw)); },
      (failure: unknown) => { if (live) setError(failure instanceof Error ? failure.message : "Rozdíl se nenačetl."); },
    );
    return () => { live = false; };
  }, [branch.name, branch.sha, target]);

  const accept = () => onAct(api("/api/pletor/linie/accept", { branch: branch.name, sha: branch.sha, target, note }), `Přijato ${shortSha(branch.sha)} do ${target}.`);
  const revoke = () => onAct(api(`/api/pletor/linie/accept/${encodeURIComponent(branch.name)}`, {}, "DELETE"), `Přijetí ${branch.name} zrušeno.`);

  return (
    <section className="pletor-dashboard__setting" aria-label={`Detail ${branch.name}`}>
      <h2 className="pletor-dashboard__group-title">{branch.name} → {target || "bez rodiče"}</h2>
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      {!target && <p className="pletor-dashboard__note">Větev nemá rodiče, není s čím porovnat.</p>}
      {target && !diff && !error && <p className="pletor-dashboard__note" role="status">Načítám rozdíl…</p>}
      {diff && (
        <>
          <p className="pletor-dashboard__note">{diffSentence(target, diff)}</p>
          <ul className="pletor-dashboard__messages">
            {diff.commits.map((commit) => <li key={commit.sha7} className="pletor-dashboard__mono">{commit.sha7} {commit.title}</li>)}
          </ul>
          {diff.stat && <pre className="pletor-dashboard__pre">{diff.stat}</pre>}
        </>
      )}
      {canAccept(branch) && target && (
        <div className="pletor-dashboard__tools">
          <input className="pletor-dashboard__input" aria-label="Poznámka k přijetí" placeholder="poznámka" value={note} onChange={(event) => setNote(event.target.value)} />
          <button type="button" className="pletor-dashboard__button" onClick={accept}>Přijmout hlavu {shortSha(branch.sha)} do {target}</button>
          {branch.acceptance && <button type="button" className="pletor-dashboard__button" onClick={revoke}>Zrušit přijetí</button>}
        </div>
      )}
    </section>
  );
}
