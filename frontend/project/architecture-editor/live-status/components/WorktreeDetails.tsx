import { useState } from "react";
import type { LiveWorktree } from "../logic/live-model";
import { sessionTitle, type SessionRequest } from "../logic/session-state";
import { archiveBlocked } from "../logic/worktree-archive";
import ArchiveConfirm from "./ArchiveConfirm";

/** Akce živého panelu nad vybraným worktree; jdou nahoru do App (přepnutí, relace) nebo do editoru (skladiště). */
export type WorktreeActions = {
  currentWorkspace: string;
  onSwitch: (id: string) => void;
  onStartSession: (request: SessionRequest) => void;
  /** Přesun do skladiště s důvodem; odmítnutí backendu přijde jako výjimka. */
  onArchive?: (id: string, reason: string) => Promise<void>;
};

/**
 * Detail vybraného worktree pod stromem: přepnutí prostoru, nová relace worktree a nová relace pro
 * každou kartu v práci. Tlačítka jsou jen tady, aby se ve stromu neopakovala u každého řádku.
 * Na konci tichá cesta do skladiště, vždy přes potvrzení s důvodem.
 */
export default function WorktreeDetails({ worktree, actions }: { worktree: LiveWorktree; actions: WorktreeActions }) {
  const [archiving, setArchiving] = useState(false);
  const name = worktree.branch || worktree.id;
  const current = actions.currentWorkspace === worktree.id;
  const blocked = archiveBlocked(worktree.id, actions.currentWorkspace);
  const onArchive = actions.onArchive;
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
    {onArchive && !archiving && <div className="live-status__archive-row">
      <button type="button" className="live-status__quiet" disabled={!!blocked} title={blocked || "Uzavřít worktree a přesunout ho do skladiště"} data-testid={"worktree-archive-" + worktree.id}
        onClick={() => setArchiving(true)}>Do skladiště…</button>
      {blocked && <small className="live-status__archive-note">{blocked}</small>}
    </div>}
    {onArchive && archiving && <ArchiveConfirm key={worktree.id} name={name} onConfirm={(reason) => onArchive(worktree.id, reason)} onCancel={() => setArchiving(false)}/>}
  </section>;
}
