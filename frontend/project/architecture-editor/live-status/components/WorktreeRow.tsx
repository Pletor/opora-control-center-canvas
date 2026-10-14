import type { LiveWorktree } from "../logic/live-model";
import { sessionTitle, WORKTREE_STATE, type SessionRequest } from "../logic/session-state";
import SessionChip from "./SessionChip";

/** Akce živého panelu; na přehledu domén chybí a strom je jen ke čtení. */
export type WorktreeActions = {
  currentWorkspace: string;
  onSwitch: (id: string) => void;
  onStartSession: (request: SessionRequest) => void;
};

/** Jeden worktree ve stromu: větev, aktér a stav slovem; rozbalený ukáže relace, karty v práci a akce. */
export default function WorktreeRow({ worktree, expanded, selected, actions, onToggle, onSelect }: {
  worktree: LiveWorktree; expanded: boolean; selected: boolean; actions?: WorktreeActions;
  onToggle: () => void; onSelect?: () => void;
}) {
  const state = WORKTREE_STATE[worktree.state];
  const name = worktree.branch || worktree.id;
  const current = actions?.currentWorkspace === worktree.id;
  return <li role="treeitem" aria-expanded={expanded} aria-selected={selected} className="live-status__item" data-testid={"worktree-" + worktree.id}>
    <div className={"live-status__row" + (selected ? " live-status__row--selected" : "")}>
      <button type="button" className="live-status__toggle" aria-label={(expanded ? "Sbalit " : "Rozbalit ") + name} onClick={onToggle}>{expanded ? "▾" : "▸"}</button>
      <button type="button" className="live-status__name" title={`Worktree ${worktree.id}`} onClick={onSelect ?? onToggle}>
        <span className="live-status__branch">{name}</span>
        {worktree.actor && <span className="live-status__actor">{worktree.actor}</span>}
      </button>
      <span className={`live-status__chip live-status__chip--${worktree.state}`} title={worktree.reasons.join("; ") || state.label}>
        <span className="live-status__icon" aria-hidden="true">{state.icon}</span>{state.label}
      </span>
    </div>
    {expanded && <ul role="group" className="live-status__group">
      {worktree.sessions.length > 0 && <li role="none" className="live-status__sessions">
        {worktree.sessions.map((session) => <SessionChip key={session.source + session.id} session={session}/>)}
      </li>}
      {worktree.cards.map((card) => <li role="treeitem" aria-selected={false} key={card.nodeId} className="live-status__card">
        <span className="live-status__card-name" title={card.nodeId}>{card.name}</span>
        {actions && <button type="button" className="live-status__quiet" onClick={() => actions.onStartSession({ workspace: worktree.id, nodeId: card.nodeId, title: sessionTitle("card", card.name) })}>Nová relace pro kartu</button>}
      </li>)}
      {!worktree.cards.length && <li role="none" className="live-status__empty">Žádná karta v práci.</li>}
      {actions && <li role="none" className="live-status__actions">
        <button type="button" className="live-status__primary" disabled={current} data-testid={"worktree-switch-" + worktree.id} onClick={() => actions.onSwitch(worktree.id)}>{current ? "Právě zde pracujete" : "Pracovat v tomto worktree"}</button>
        <button type="button" className="live-status__quiet" data-testid={"worktree-session-" + worktree.id} onClick={() => actions.onStartSession({ workspace: worktree.id, nodeId: null, title: sessionTitle("worktree", name) })}>Nová relace</button>
      </li>}
    </ul>}
  </li>;
}
