import type { LiveDomain } from "../logic/live-model";
import "../styles/live-status.css";
import { countsLine } from "../logic/live-model";
import type { WebView } from "../logic/web-slots";
import LiveWebSection from "./LiveWebSection";
import WorktreeDetails, { type WorktreeActions } from "./WorktreeDetails";
import WorktreeTree from "./WorktreeTree";
import type { WorktreeNav } from "./WorktreeRow";

export type LiveWorkView = { domain: LiveDomain | null; loaded: boolean; stale: string; loading: boolean; error: string };

/**
 * Dříve pravý sloupec Mapy domény, teď nikde složený (jen u projektů s worktree): nahoře stav webu hostu (mobilní aplikace web nemá, `web = null`), pod ním worktree
 * domény se stavy relací a pod stromem akce vybraného worktree. Data dostává hotová; obnovení webu,
 * výběr worktree, přepnutí prostoru, otevření karty či relace a nové relace hlásí nahoru.
 * `aria-live` oblast čte jen věty o změně stavu, ne každé kolo pollingu.
 */
export default function LiveDomainPanel({ web, work, announcement, selectedWorktreeId, actions, nav, onRefreshWeb, onSelectWorktree, onCreateWorktree }: {
  web: WebView | null; work: LiveWorkView; announcement: string; selectedWorktreeId: string | null; actions: WorktreeActions; nav: WorktreeNav;
  onRefreshWeb: () => void; onSelectWorktree: (id: string | null) => void; onCreateWorktree: () => void;
}) {
  const worktrees = work.domain?.worktrees ?? [];
  const selected = worktrees.find((item) => item.id === selectedWorktreeId);
  return <aside className="live-status" aria-label="Živý stav domény" data-testid="live-domain-panel">
    {web && <LiveWebSection web={web} onRefresh={onRefreshWeb}/>}
    <section className="live-status__section">
      <header className="live-status__head">
        <h3 className="live-status__title">Worktree</h3>
        {work.domain && <span className="live-status__counts">{countsLine(work.domain.counts)}</span>}
      </header>
      {work.stale && <small className="live-status__stale">{work.stale}</small>}
      {work.error && !work.stale && <small className="live-status__stale" role="alert">Stav práce se nepodařilo načíst: {work.error}</small>}
      {!work.loaded && work.loading && <p className="live-status__empty">Načítám stav práce…</p>}
      {worktrees.length > 0 && <WorktreeTree worktrees={worktrees} label="Worktree domény" selectedId={selectedWorktreeId} nav={nav} onSelect={onSelectWorktree}/>}
      {work.loaded && !worktrees.length && <div className="live-status__idle">
        <p className="live-status__empty">Na této doméně se teď nepracuje.</p>
        <button type="button" className="live-status__primary" data-testid="live-new-worktree" onClick={onCreateWorktree}>Nový worktree</button>
      </div>}
      {selected ? <WorktreeDetails key={selected.id} worktree={selected} actions={actions}/>
        : worktrees.length > 0 && <p className="live-status__empty">Vyberte worktree a pod stromem se ukážou jeho akce.</p>}
      {worktrees.length > 0 && <button type="button" className="live-status__quiet live-status__new" onClick={onCreateWorktree}>+ Nový worktree</button>}
    </section>
    <p className="live-status__announce" aria-live="polite">{announcement}</p>
  </aside>;
}
