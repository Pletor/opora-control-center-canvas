import { useState } from "react";
import { countsLine, type LiveWorktree, type LiveCounts } from "@/project/architecture-editor/live-status/logic/live-model";
import WorktreeTree from "@/project/architecture-editor/live-status/components/WorktreeTree";

/** Práce na doméně v kartě přehledu: věta s počty, která rozbalí stěsnaný strom worktree jen ke čtení. */
export default function DomainWork({ counts, worktrees, label }: { counts: LiveCounts; worktrees: LiveWorktree[]; label: string }) {
  const [open, setOpen] = useState(false);
  if (!counts.total) return <p className="arch-landing__work arch-landing__work--idle">Na této doméně se teď nepracuje.</p>;
  return <div className="arch-landing__work">
    <button type="button" className="arch-landing__work-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
      <span aria-hidden="true">{open ? "▾" : "▸"}</span> {countsLine(counts)}
    </button>
    {open && <WorktreeTree worktrees={worktrees} label={label} compact/>}
  </div>;
}
