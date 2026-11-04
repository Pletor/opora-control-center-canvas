// Čekající návrh srdce pro rodiče `SiteAdmin`: načtení, přijetí nad revizí stránky a zamítnutí. Po přijetí rodič
// načte uložený dokument znovu (`onAccepted`); 409 = návrh je zastaralý nebo dokument mezitím někdo uložil.
import { useCallback, useEffect, useState } from "react";
import { acceptProposal, loadProposal, rejectProposal, type SiteProposal } from "./site-proposals";

const message = (error: unknown) => error instanceof Error ? error.message : String(error);

export function useSiteProposals(project: string, revision: number, onAccepted: () => void) {
  const [proposal, setProposal] = useState<SiteProposal | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const refresh = useCallback(() => { loadProposal(project).then(setProposal, () => setProposal(null)); }, [project]);
  useEffect(refresh, [refresh, revision]);
  async function decide(accept: boolean) {
    if (!proposal || busy) return;
    setBusy(true); setError("");
    try {
      if (accept) { await acceptProposal(project, proposal.id, revision); onAccepted(); }
      else await rejectProposal(project, proposal.id);
      refresh();
    } catch (failure) { setError(message(failure)); refresh(); }
    finally { setBusy(false); }
  }
  return { proposal, busy, error, accept: () => decide(true), reject: () => decide(false) };
}
