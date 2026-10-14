import type { LiveDomain } from "../logic/live-model";
import "../styles/live-status.css";
import { countsLine } from "../logic/live-model";
import type { WebHost } from "../logic/web-status";
import WebStatusBadge from "./WebStatusBadge";
import WorktreeTree from "./WorktreeTree";
import type { WorktreeActions } from "./WorktreeRow";

export type LiveWebView = { host: WebHost | null; stale: string; loading: boolean; error: string };
/** `null` = projekt worktree nemá (schopnost `worktreeLive`), panel ukáže jen web. */
export type LiveWorkView = { domain: LiveDomain | null; loaded: boolean; stale: string; loading: boolean; error: string } | null;

/**
 * Pravý sloupec mapy domény: nahoře stav webu hostu, pod ním worktree domény se stavy relací.
 * Data dostává hotová; obnovení webu, výběr worktree, přepnutí prostoru a nové relace hlásí nahoru.
 * `aria-live` oblast čte jen věty o změně stavu, ne každé kolo pollingu.
 */
export default function LiveDomainPanel({ web, work, announcement, selectedWorktreeId, actions, onRefreshWeb, onSelectWorktree, onCreateWorktree }: {
  web: LiveWebView; work: LiveWorkView; announcement: string; selectedWorktreeId: string | null; actions: WorktreeActions;
  onRefreshWeb: () => void; onSelectWorktree: (id: string | null) => void; onCreateWorktree: () => void;
}) {
  const worktrees = work?.domain?.worktrees ?? [];
  return <aside className="live-status" aria-label="Živý stav domény" data-testid="live-domain-panel">
    <section className="live-status__section">
      <header className="live-status__head">
        <h3 className="live-status__title">Web</h3>
        <button type="button" className="live-status__quiet" disabled={web.loading} onClick={onRefreshWeb} title="Ověří host znovu; backend drží výsledek 60 s.">{web.loading ? "Ověřuji…" : "Ověřit znovu"}</button>
      </header>
      <WebStatusBadge host={web.host} stale={web.stale}/>
      {web.host && <code className="live-status__host">{web.host.host}</code>}
      {web.stale && <small className="live-status__stale">{web.stale}</small>}
      {web.error && !web.stale && <small className="live-status__stale" role="alert">{web.error}</small>}
    </section>
    {work && <section className="live-status__section">
      <header className="live-status__head">
        <h3 className="live-status__title">Worktree</h3>
        {work.domain && <span className="live-status__counts">{countsLine(work.domain.counts)}</span>}
      </header>
      {work.stale && <small className="live-status__stale">{work.stale}</small>}
      {work.error && !work.stale && <small className="live-status__stale" role="alert">{work.error}</small>}
      {!work.loaded && work.loading && <p className="live-status__empty">Načítám stav práce…</p>}
      {worktrees.length > 0 && <WorktreeTree worktrees={worktrees} label="Worktree domény" selectedId={selectedWorktreeId} actions={actions} onSelect={onSelectWorktree}/>}
      {work.loaded && !worktrees.length && <div className="live-status__idle">
        <p className="live-status__empty">Na této doméně se teď nepracuje.</p>
        <button type="button" className="live-status__primary" data-testid="live-new-worktree" onClick={onCreateWorktree}>Nový worktree</button>
      </div>}
      {worktrees.length > 0 && <button type="button" className="live-status__quiet live-status__new" onClick={onCreateWorktree}>+ Nový worktree</button>}
    </section>}
    <p className="live-status__announce" aria-live="polite">{announcement}</p>
  </aside>;
}
