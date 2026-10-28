import { worktreeBadgeText, worktreeLabel, type WorktreeTally } from "../logic/worktree-tally";
import "../styles/worktree-badge.css";

/** Odznak práce ve worktree na kartě (Studio, Mapa domény): ikona větve a jméno větve, u víc worktree „2 worktree“;
 * celá věta (větve a aktéři) v title i pro čtečku. Bez worktree nic. Jen kresba, data skládá rodič. */
export default function WorktreeBadge({ worktree, testId }: { worktree: WorktreeTally | null | undefined; testId?: string }) {
  if (!worktree) return null;
  const label = worktreeLabel(worktree);
  return <span className="worktree-badge" role="img" aria-label={label} title={label} data-testid={testId} data-count={worktree.count}>
    <svg className="worktree-badge__branch" aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
      <line x1="6" x2="6" y1="3" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>
    </svg>
    <span className="worktree-badge__name">{worktreeBadgeText(worktree)}</span>
  </span>;
}
