// Tokeny Design systému projektu (dokument Správy webu, `GET /api/site-admin?project=`) pro pruh Design webu a změny
// tokenů v panelu skenu. Chyba čtení = `null`: plátno pracuje dál, pruh řekne, že design nejde načíst. `reload` po zápisu.
import { useCallback, useEffect, useState } from "react";
import { loadSiteAdmin } from "@/project/site-admin/logic/site-admin-api";
import type { DesignTokens } from "@/project/site-admin/logic/site-document";

export function useDesignTokens(project: string): { tokens: DesignTokens | null; reload: () => void } {
  const [tokens, setTokens] = useState<DesignTokens | null>(null);
  const [round, setRound] = useState(0);
  useEffect(() => {
    let alive = true;
    loadSiteAdmin(project).then((view) => { if (alive) setTokens(view.document.design.tokens); }, () => { if (alive) setTokens(null); });
    return () => { alive = false; };
  }, [project, round]);
  return { tokens, reload: useCallback(() => setRound((value) => value + 1), []) };
}
