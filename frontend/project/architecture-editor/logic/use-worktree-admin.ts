// Správa worktree z editoru architektury (docs/domeny-a-worktree.md §6, §9): přiřazení worktree
// k doméně (`PATCH /api/workspaces/{wid}`), přesun do skladiště (`POST …/archive`) a seznam skladiště
// jen ke čtení (`GET /api/workspaces/archive`). Dílky volají jen callbacky; chyba backendu (i 404/405,
// když endpoint ještě neběží) se vrátí jako text výjimky, kterou dílek ukáže u své akce.
import { useCallback, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { emptyShelf, normalizeArchive, reasonProblem, type ArchiveShelfState } from "../live-status/logic/worktree-archive";

const messageOf = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));
const workspaceUrl = (wid: string) => "/api/workspaces/" + encodeURIComponent(wid);

export type WorktreeAdmin = {
  shelf: ArchiveShelfState;
  loadShelf: () => void;
  assign: (worktreeId: string, domainId: string) => Promise<void>;
  archive: (worktreeId: string, reason: string) => Promise<void>;
};

/** `onChanged` po úspěchu obnoví stav práce a seznam prostorů v App. */
export function useWorktreeAdmin(project: string, onChanged: () => void): WorktreeAdmin {
  const [shelf, setShelf] = useState(emptyShelf);
  const ticket = useRef(0);
  const changed = useRef(onChanged);
  changed.current = onChanged;

  const loadShelf = useCallback(() => {
    const mine = ++ticket.current;
    setShelf((state) => ({ ...state, loading: true, error: "" }));
    api<unknown>("/api/workspaces/archive?" + new URLSearchParams({ project })).then(
      (raw) => { if (mine === ticket.current) setShelf({ items: normalizeArchive(raw), loading: false, error: "" }); },
      (cause) => { if (mine === ticket.current) setShelf((state) => ({ ...state, loading: false, error: messageOf(cause) })); },
    );
  }, [project]);

  const assign = useCallback(async (worktreeId: string, domainId: string) => {
    if (!domainId) throw new Error("Vyberte doménu.");
    await api(workspaceUrl(worktreeId), { project, nodeId: domainId }, "PATCH");
    changed.current();
  }, [project]);

  const archive = useCallback(async (worktreeId: string, reason: string) => {
    const problem = reasonProblem(reason);
    if (problem) throw new Error(problem);
    await api(workspaceUrl(worktreeId) + "/archive", { project, reason: reason.trim(), confirmed: true });
    changed.current();
    if (shelf.items !== null) loadShelf();
  }, [project, shelf.items, loadShelf]);

  return { shelf, loadShelf, assign, archive };
}
