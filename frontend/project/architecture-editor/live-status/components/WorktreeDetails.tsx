import { useState } from "react";
import type { HeartRequest } from "@/layout/heart-channel/logic/heart-api";
import type { LiveWorktree } from "../logic/live-model";
import { heartText } from "../logic/session-state";
import { archiveBlocked } from "../logic/worktree-archive";
import ArchiveConfirm from "./ArchiveConfirm";
import { worktreeLabel, worktreeName } from "../logic/worktree-label";

/** Akce živého panelu nad vybraným worktree; jdou nahoru do App (přepnutí, zpráva srdci) nebo do editoru (skladiště). */
export type WorktreeActions = {
  currentWorkspace: string;
  onSwitch: (id: string) => void;
  /** Připravený text pro srdce; App ho odešle a otevře panel asistenta. */
  onAskHeart: (request: HeartRequest) => void;
  /** Přesun do skladiště s důvodem; odmítnutí backendu přijde jako výjimka. */
  onArchive?: (id: string, reason: string) => Promise<void>;
};

/**
 * Detail vybraného worktree pod stromem: přepnutí prostoru, zadání srdci pro worktree a pro
 * každou kartu v práci. Tlačítka jsou jen tady, aby se ve stromu neopakovala u každého řádku.
 * Na konci tichá cesta do skladiště, vždy přes potvrzení s důvodem.
 */
export default function WorktreeDetails({ worktree, actions }: { worktree: LiveWorktree; actions: WorktreeActions }) {
  const [archiving, setArchiving] = useState(false);
  const name = worktreeName(worktree);
  const label = worktreeLabel(worktree);
  const current = actions.currentWorkspace === worktree.id;
  const blocked = archiveBlocked(worktree.id, actions.currentWorkspace);
  const onArchive = actions.onArchive;
  return <section className="live-status__details" aria-label={`Akce worktree ${name}`} data-testid={"worktree-details-" + worktree.id}>
    <p className="live-status__details-title" title={label.tooltip}>{name}</p>
    {label.branch && <code className="live-status__details-branch" title={label.branch}>{label.branch}</code>}
    <div className="live-status__actions">
      <button type="button" className="live-status__primary" disabled={current} data-testid={"worktree-switch-" + worktree.id} onClick={() => actions.onSwitch(worktree.id)}>{current ? "Právě zde pracujete" : "Pracovat v tomto worktree"}</button>
      <button type="button" className="live-status__quiet" title="Poslat srdci zadání pro tento worktree" data-testid={"worktree-heart-" + worktree.id} onClick={() => actions.onAskHeart({ workspace: worktree.id, text: heartText("worktree", name) })}>Zadat srdci</button>
    </div>
    {worktree.cards.length > 0 && <>
      <p className="live-status__details-label">Zadat srdci kartu</p>
      <ul className="live-status__card-actions">
        {worktree.cards.map((card) => <li key={card.nodeId}>
          <button type="button" className="live-status__quiet" title={`Poslat srdci zadání pro kartu ${card.name}`} data-testid={"worktree-card-heart-" + card.nodeId}
            onClick={() => actions.onAskHeart({ workspace: worktree.id, text: heartText("card", name, card) })}>{card.name}</button>
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
