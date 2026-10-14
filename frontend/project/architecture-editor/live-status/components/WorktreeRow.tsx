import type { MouseEvent } from "react";
import type { LiveWorktree } from "../logic/live-model";
import { WORKTREE_STATE, type CardRequest } from "../logic/session-state";
import { worktreeKey, type TreeItem } from "../logic/tree-nav";
import SessionChip from "./SessionChip";

/** Otevření z řádku stromu: karta (App přepne prostor a vybere ji) a relace asistenta (panel Asistent). */
export type WorktreeNav = { onOpenCard: (request: CardRequest) => void; onOpenSession: (id: string) => void };

/** Co řádek potřebuje od stromu: zastávku Tab, registraci prvků pro fokus a použití položky. */
export type RowFocus = { tabStop: string | null; register: (key: string) => (element: HTMLLIElement | null) => void; onActivate: (item: TreeItem) => void };

/**
 * Jeden worktree ve stromu: větev, aktér a stav slovem; rozbalený ukáže relace a karty v práci jako
 * podřízené položky. Akce (přepnutí, nové relace) tu nejsou, patří do detailu vybraného worktree.
 */
export default function WorktreeRow({ worktree, expanded, selected, nav, focus, onToggle }: {
  worktree: LiveWorktree; expanded: boolean; selected: boolean; nav?: WorktreeNav; focus: RowFocus; onToggle: () => void;
}) {
  const state = WORKTREE_STATE[worktree.state];
  const name = worktree.branch || worktree.id;
  const head = worktreeKey(worktree.id);
  const leaf = (key: string, kind: TreeItem["kind"], targetId: string) => ({
    role: "treeitem", "aria-level": 2, "aria-selected": false, tabIndex: focus.tabStop === key ? 0 : -1, "data-tree-key": key, ref: focus.register(key),
    onClick: (event: MouseEvent) => { event.stopPropagation(); focus.onActivate({ key, level: 2, worktreeId: worktree.id, kind, targetId }); },
  }) as const;
  return <li role="treeitem" aria-level={1} aria-expanded={expanded} aria-selected={selected} tabIndex={focus.tabStop === head ? 0 : -1} data-tree-key={head} ref={focus.register(head)}
    className="live-status__item" data-testid={"worktree-" + worktree.id}>
    <div className={"live-status__row" + (selected ? " live-status__row--selected" : "")} onClick={() => focus.onActivate({ key: head, level: 1, worktreeId: worktree.id, kind: "worktree", targetId: worktree.id })}>
      <button type="button" tabIndex={-1} className="live-status__toggle" aria-label={(expanded ? "Sbalit " : "Rozbalit ") + name} onClick={(event) => { event.stopPropagation(); onToggle(); }}>{expanded ? "▾" : "▸"}</button>
      <span className="live-status__name" title={`Worktree ${worktree.id}`}>
        <span className="live-status__branch">{name}</span>
        {worktree.actor && <span className="live-status__actor">{worktree.actor}</span>}
      </span>
      <span className={`live-status__chip live-status__chip--${worktree.state}`} title={worktree.reasons.join("; ") || state.label}>
        <span className="live-status__icon" aria-hidden="true">{state.icon}</span>{state.label}
      </span>
    </div>
    {expanded && <ul role="group" className="live-status__group">
      {worktree.sessions.map((session) => <li key={session.source + session.id} className="live-status__leaf" {...leaf(`s:${worktree.id}:${session.source}:${session.id}`, "session", session.id)}>
        <SessionChip session={session} effective={worktree.state} onOpen={nav && (() => nav.onOpenSession(session.id))}/>
      </li>)}
      {worktree.cards.map((card) => <li key={card.nodeId} className="live-status__leaf" {...leaf(`c:${worktree.id}:${card.nodeId}`, "card", card.nodeId)}>
        {nav ? <button type="button" tabIndex={-1} className="live-status__card-name live-status__card-name--link" title={`Otevřít kartu ${card.name} ve worktree ${name}`} data-testid={"worktree-card-" + card.nodeId}
          onClick={(event) => { event.stopPropagation(); nav.onOpenCard({ workspace: worktree.id, nodeId: card.nodeId }); }}>{card.name}</button>
          : <span className="live-status__card-name" title={card.nodeId}>{card.name}</span>}
      </li>)}
      {!worktree.cards.length && <li role="none" className="live-status__empty">Žádná karta v práci.</li>}
    </ul>}
  </li>;
}
