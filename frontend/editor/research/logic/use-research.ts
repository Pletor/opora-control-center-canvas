import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { archiveResearch, loadResearch, loadResearchDetail, loadResearchEdge, loadResearchEvents, requestGate } from "./research-api";
import type { ResearchDetail, ResearchEdgeDetail, ResearchGraph, ResearchScope } from "./research-types";
const message = (error: unknown) => error instanceof Error ? error.message : String(error);
export function useResearch(scope: ResearchScope, archived: boolean) {
  const gate = useMemo(requestGate, [scope.project, scope.workspace, archived]);
  const eventState = useMemo(() => ({ cursor: 0, workspace: "", initialized: false }), [gate]);
  const alive = useRef(true); const writeLock = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [data, setData] = useState<ResearchGraph>({ cards: [], edges: [] });
  const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [writing, setWriting] = useState(false);
  useEffect(() => { setData({ cards: [], edges: [] }); setLoading(true); return () => gate.invalidate(); }, [gate]);
  const reload = useCallback(async () => {
    const ticket = gate.begin();
    try { const result = await loadResearch(scope, archived); if (gate.accepts(ticket)) { setData(result); setError(""); return true; } }
    catch (reason) { if (gate.accepts(ticket)) setError(message(reason)); }
    finally { if (gate.accepts(ticket)) setLoading(false); }
  }, [scope.project, scope.workspace, archived, gate]);
  const poll = useCallback(async () => {
    const ticket = gate.begin();
    try {
      const changes = await loadResearchEvents(scope, eventState.cursor);
      if (!gate.accepts(ticket)) return;
      // main can resolve to a different active workspace; never carry its old cursor across scopes.
      const changedScope = !!eventState.workspace && eventState.workspace !== changes.workspace;
      if (changedScope) {
        eventState.cursor = 0; eventState.initialized = false;
      }
      eventState.workspace = changes.workspace;
      if (!eventState.initialized || changes.events.length) {
        if (!await reload()) return;
      }
      // On scope switches start from zero next time so no update can be skipped.
      eventState.cursor = changedScope ? 0 : changes.nextCursor;
      eventState.initialized = true; setError("");
    } catch (reason) { if (gate.accepts(ticket)) { setError(message(reason)); setLoading(false); } }
  }, [scope.project, scope.workspace, gate, eventState, reload]);
  usePolling(poll, { intervalMs: 8000, refreshKeys: [scope.project, scope.workspace, archived] });
  const archive = async (entity: "card" | "edge", id: string, revision: number, value: boolean) => {
    if (writeLock.current) return false; writeLock.current = true; setWriting(true); setError("");
    try { await archiveResearch({ ...scope, workspace: data.workspace ?? scope.workspace }, entity, id, revision, value); if (!alive.current) return false; await reload(); return true; }
    catch (reason) { if (alive.current) setError(message(reason)); return false; }
    finally { writeLock.current = false; if (alive.current) setWriting(false); }
  };
  return { ...data, loading, error, writing, reload, archive };
}
export function useResearchDetail(scope: ResearchScope, id: string | null, revision: number | undefined, currentRevision?: number) {
  const [detail, setDetail] = useState<ResearchDetail | null>(null); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  useEffect(() => {
    let alive = true; setDetail(null); setError(""); setLoading(!!id);
    if (id) loadResearchDetail(scope, id, revision).then(result => { if (alive) setDetail(result); })
      .catch(reason => { if (alive) setError(message(reason)); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [scope.project, scope.workspace, id, revision, currentRevision]);
  return { detail: detail?.card.id === id && (revision === undefined || detail.card.revision === revision) ? detail : null, loading, error };
}

export function useResearchEdge(scope: ResearchScope, id: string | null, revision: number | undefined, currentRevision?: number) {
  const [detail, setDetail] = useState<ResearchEdgeDetail | null>(null); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  useEffect(() => {
    let alive = true; setDetail(null); setError(""); setLoading(!!id);
    if (id) loadResearchEdge(scope, id, revision).then(result => { if (alive) setDetail(result); })
      .catch(reason => { if (alive) setError(message(reason)); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [scope.project, scope.workspace, id, revision, currentRevision]);
  return { detail: detail?.edge.id === id && (revision === undefined || detail.edge.revision === revision) ? detail : null, loading, error };
}
