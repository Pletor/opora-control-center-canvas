import WorktreeTree from "@/project/architecture-editor/live-status/components/WorktreeTree";
import type { WorktreeNav } from "@/project/architecture-editor/live-status/components/WorktreeRow";
import type { LiveWorktree } from "@/project/architecture-editor/live-status/logic/live-model";
import type { DomainChoice } from "../logic/domain-choices";
import AssignDomainRow from "./AssignDomainRow";

/**
 * Skupina Nepřiřazené: worktree bez domény (starší `node_id = "project"`). Strom ukáže jejich práci,
 * pod ním je u každého „Přiřadit k doméně“, aby se worktree dostal do správného pruhu.
 */
export default function UnassignedWorktrees({ worktrees, choices, stale, nav, onAssign }: {
  worktrees: LiveWorktree[]; choices: DomainChoice[]; stale: string; nav?: WorktreeNav;
  onAssign?: (worktreeId: string, domainId: string) => Promise<void>;
}) {
  return <section className="arch-landing__group" data-testid="architecture-unassigned">
    <h3 className="arch-landing__group-title"><span className="arch-landing__tag arch-landing__tag--legacy">Nepřiřazené</span><span className="arch-landing__note">Worktree, které zatím nepatří žádné doméně.</span>
      {stale && <small className="arch-landing__stale">{stale}</small>}</h3>
    <WorktreeTree worktrees={worktrees} label="Nepřiřazené worktree" compact nav={nav}/>
    {onAssign && <div className="arch-landing__assign-list">
      {worktrees.map((item) => <AssignDomainRow key={item.id} worktreeId={item.id} name={item.branch || item.id} choices={choices} onAssign={onAssign}/>)}
    </div>}
  </section>;
}
