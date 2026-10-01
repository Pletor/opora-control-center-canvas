// Síťový stav souhrnu kapitol v módu Text (`docs/souhrn-prace-agentu.md`). Levný souhrn paměti všech
// karet přijde jedním dotazem; plný stav karty (komunikace, ověření, další krok) jen z node-briefu, a
// ten se načítá výhradně pro rozbalené kapitoly a vždy jen jeden najednou — brief drží zámek plátna.
// Hook drží rodič (TextWorkspace) a výsledek rozdá dílkům v props. Odpověď ze starého rozsahu nebo
// po odpojení se zahodí (lístek jako v `use-agent-orientation.ts`).
import { useCallback, useEffect, useRef, useState } from "react";
import { briefReadOnlyFlags, overviewModel } from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import type { AgentWorkspaceRecord } from "@/editor/node-detail/agent-workspace/logic/agent-workspace";
import type { ChapterWork, OverviewEntry } from "@/editor/node-detail/agent-summary/logic/agent-summary";
import { markLoading, nextStale, staleIds, worksFrom } from "@/editor/node-detail/agent-summary/logic/chapter-queue";
import { fetchAgentWorkspaceSummaries, fetchNodeBrief } from "@/shared/desktop-state/logic/api";

/** Změny revize plátna chodí v dávkách; souhrn se obnoví až po chvíli klidu. */
export const REFRESH_DEBOUNCE_MS = 1500;

export type ChapterOverviewsInput = {
  project: string;
  workspace: string;
  /** Rozbalené karty v pořadí kapitol, bez komentářů; v tomhle pořadí se načítají briefy. */
  expandedIds: readonly string[];
  /** Otisk stavu plátna (digest + revize); jeho změna po 1500 ms obnoví souhrn i rozbalené briefy. */
  refreshKey?: string;
};

export type ChapterOverviews = {
  works: Record<string, ChapterWork>;
  worksReadOnly: boolean;
  overviews: Record<string, OverviewEntry>;
  refresh: () => void;
};

export function useChapterOverviews({ project, workspace, expandedIds, refreshKey = "" }: ChapterOverviewsInput): ChapterOverviews {
  const [works, setWorks] = useState<Record<string, ChapterWork>>({});
  const [worksReadOnly, setWorksReadOnly] = useState(false);
  const [overviews, setOverviews] = useState<Record<string, OverviewEntry>>({});
  const [generation, setGeneration] = useState(0);
  const scope = `${project}\u0000${workspace}`;
  const expandedKey = expandedIds.join("\u0000");
  const latest = useRef({ project, workspace, expandedIds, generation });
  latest.current = { project, workspace, expandedIds, generation };
  const ticket = useRef(0);
  const worksTicket = useRef(0);
  const busy = useRef(false);
  const loadedAt = useRef(new Map<string, number>());
  const lastRefreshKey = useRef(refreshKey);
  const refresh = useCallback(() => setGeneration((value) => value + 1), []);

  // Nový rozsah = nový svět: rozběhnutý brief se zahodí a žádný záznam se nepřenáší.
  useEffect(() => {
    ticket.current += 1;
    busy.current = false;
    loadedAt.current = new Map();
    setOverviews({});
    setWorks({});
    setWorksReadOnly(false);
    return () => { ticket.current += 1; };
  }, [scope]);

  useEffect(() => {
    const current = ++worksTicket.current;
    fetchAgentWorkspaceSummaries(project, workspace)
      .then((value) => {
        if (current !== worksTicket.current) return;
        const parsed = worksFrom(value);
        setWorks(parsed.works);
        setWorksReadOnly(parsed.readOnly);
      })
      // Nenačtený souhrn nic nenuluje: hlavičky zůstanou u posledního známého stavu.
      .catch(() => undefined);
    return () => { worksTicket.current += 1; };
  }, [scope, generation]);

  // Dávka změn plátna → jedna obnova po chvíli klidu. Návrat na tentýž otisk obnovu zruší.
  useEffect(() => {
    if (refreshKey === lastRefreshKey.current) return;
    const timer = window.setTimeout(() => {
      lastRefreshKey.current = refreshKey;
      setGeneration((value) => value + 1);
    }, REFRESH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [refreshKey]);

  const pump = useRef<() => void>(() => undefined);
  pump.current = () => {
    if (busy.current) return;
    const { project: p, workspace: w, expandedIds: ids, generation: gen } = latest.current;
    const id = nextStale(ids, loadedAt.current, gen);
    if (!id) return;
    busy.current = true;
    const current = ticket.current;
    const settle = (entry: OverviewEntry) => {
      if (current !== ticket.current) return;
      loadedAt.current.set(id, gen);
      // Obnova přišla během dotazu: výsledek se ukáže, ale karta zůstává ve frontě jako „načítám“.
      const requeued = gen !== latest.current.generation && latest.current.expandedIds.includes(id);
      setOverviews((prev) => ({
        ...prev,
        [id]: requeued ? { status: "loading", overview: entry.overview ?? prev[id]?.overview ?? null } : entry,
      }));
      busy.current = false;
      pump.current();
    };
    fetchNodeBrief(p, w, id).then(
      (brief) => settle({
        status: "ready",
        overview: overviewModel(brief, (brief.agentWorkspace ?? null) as AgentWorkspaceRecord | null, briefReadOnlyFlags(brief)),
      }),
      () => settle({ status: "error", overview: null }),
    );
  };

  // Rozbalení nebo obnova: čekající kapitoly hned ukážou „načítám“ a fronta se rozběhne.
  useEffect(() => {
    const waiting = staleIds(expandedIds, loadedAt.current, generation);
    if (waiting.length) setOverviews((prev) => markLoading(prev, waiting));
    pump.current();
    // Závislost je `expandedKey` (obsah pole), ne `expandedIds`: pole je při každém renderu nové.
  }, [scope, generation, expandedKey]);

  return { works, worksReadOnly, overviews, refresh };
}
