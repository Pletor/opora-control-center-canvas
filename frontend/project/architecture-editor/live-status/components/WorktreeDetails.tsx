import type { LiveWorktree } from "../logic/live-model";
import { sessionTitle, type SessionRequest } from "../logic/session-state";

/** Akce živého panelu nad vybraným worktree; jdou nahoru do App. */
export type WorktreeActions = {
  currentWorkspace: string;
  onSwitch: (id: string) => void;
  onStartSession: (request: SessionRequest) => void;
};

/**
 * Detail vybraného worktree pod stromem: přepnutí prostoru, nová relace worktree a nová relace pro
 * každou kartu v práci. Tlačítka jsou jen tady, aby se ve stromu neopakovala u každého řádku.
 */
export default function WorktreeDetails({ worktree, actions }: { worktree: LiveWorktree; actions: WorktreeActions }) {
  const name = worktree.branch || worktree.id;
  const current = actions.currentWorkspace === worktree.id;
  return <section className="live-status__details" aria-label={`Akce worktree ${name}`} data-testid={"worktree-details-" + worktree.id}>
    <p className="live-status__details-title">{name}</p>
    <div className="live-status__actions">
      <button type="button" className="live-status__primary" disabled={current} data-testid={"worktree-switch-" + worktree.id} onClick={() => actions.onSwitch(worktree.id)}>{current ? "Právě zde pracujete" : "Pracovat v tomto worktree"}</button>
      <button type="button" className="live-status__quiet" data-testid={"worktree-session-" + worktree.id} onClick={() => actions.onStartSession({ workspace: worktree.id, nodeId: null, title: sessionTitle("worktree", name) })}>Nová relace</button>
    </div>
    {worktree.cards.length > 0 && <>
      <p className="live-status__details-label">Nová relace pro kartu</p>
      <ul className="live-status__card-actions">
        {worktree.cards.map((card) => <li key={card.nodeId}>
          <button type="button" className="live-status__quiet" title={`Nová relace asistenta pro kartu ${card.name}`} data-testid={"worktree-card-session-" + card.nodeId}
            onClick={() => actions.onStartSession({ workspace: worktree.id, nodeId: card.nodeId, title: sessionTitle("card", card.name) })}>{card.name}</button>
        </li>)}
      </ul>
    </>}
  </section>;
}
