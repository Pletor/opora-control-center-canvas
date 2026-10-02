// Vazba indexu plátna na React: s neprázdným dotazem STRÁNKY po ~200 ms zavolá `GET /api/canvas-index`
// a vrátí shody pro právě platný dotaz. Bez dotazu se nic nevolá. Dokud odpověď nedorazí, nebo když
// endpoint selže, vrací `null` a panel použije dnešní lokální filtr podle názvu. Volá ho App (rodič);
// panel Knihovny dostane jen hotové shody v props.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { canvasIndexUrl, indexMatches, type IndexMatches } from "@/layout/library-navbar/logic/canvas-index";

export const INDEX_DEBOUNCE_MS = 200;

export function useCanvasIndex(project: string, workspace: string, query: string, enabled: boolean, revision = ""): IndexMatches | null {
  const [result, setResult] = useState<{ key: string; matches: IndexMatches | null } | null>(null);
  const q = query.trim();
  const key = JSON.stringify([project, workspace, q, revision]);
  useEffect(() => {
    if (!enabled || !q) return;
    let live = true;
    const timer = setTimeout(() => {
      api<unknown>(canvasIndexUrl(project, workspace, q))
        .then((response) => { if (live) setResult({ key, matches: indexMatches(response) }); })
        .catch(() => { if (live) setResult({ key, matches: null }); });
    }, INDEX_DEBOUNCE_MS);
    return () => { live = false; clearTimeout(timer); };
  }, [key, enabled]);
  return enabled && q && result?.key === key ? result.matches : null;
}
