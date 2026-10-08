import { useCallback, useEffect, useRef, useState } from "react";
import { drainHistoryPages } from "./history-pagination";
import type { NodeBrief } from "@/shared/desktop-state/logic/types";
import type { AcceptedResult } from "@/editor/llm-control/editor-context/logic/handoff";

type HistoryPage<T> = { items?: T[]; messages?: T[]; nextBefore?: number | string | null };
type BriefPage = NodeBrief & { resultHistory?: HistoryPage<AcceptedResult> };
type Message = Record<string, unknown> & { id?: string };
export type HistoryCursors = { results: number | null; incoming: string | null; outgoing: string | null };
export type DnaHistoryState = { brief: NodeBrief | null; results: AcceptedResult[]; messages: Message[]; before: number | null; loading: boolean; loadingMore: boolean; error: string; partial: boolean; loadMore: () => Promise<void>; loadAll: () => Promise<void>; reload: () => void };
const query = (values: Record<string, string>) => new URLSearchParams(values).toString();
const errorText = (error: unknown) => error instanceof Error ? error.message : String(error);
const cursor = (value: unknown): string | null => typeof value === "number" || typeof value === "string" ? String(value) : null;
const pageItems = <T,>(page: HistoryPage<T>) => Array.isArray(page.items) ? page.items : Array.isArray(page.messages) ? page.messages : [];

/** Přidá jen nové neměnné záznamy; opakovaná stránka nesmí zdvojit časovou osu. */
export function mergeHistoryItems<T extends { id?: string }>(current: T[], page: T[]): T[] {
  return [...current, ...page.filter(item => !item.id || !current.some(old => old.id === item.id))];
}

/** Opakovaný kurzor by při „načíst vše“ vedl k nekonečné síťové smyčce. */
export function advanceHistoryCursors(current: HistoryCursors, pages: { results: HistoryPage<unknown>; incoming: HistoryPage<unknown>; outgoing: HistoryPage<unknown> }): HistoryCursors {
  const next = { results: cursor(pages.results.nextBefore), incoming: cursor(pages.incoming.nextBefore), outgoing: cursor(pages.outgoing.nextBefore) };
  if ((current.results !== null && next.results === String(current.results)) || (current.incoming !== null && next.incoming === current.incoming) || (current.outgoing !== null && next.outgoing === current.outgoing)) throw new Error("Kurzor historie se neoposunul.");
  return { results: next.results === null ? null : Number(next.results), incoming: next.incoming, outgoing: next.outgoing };
}

/** Jeden lazy zdroj pro Proces i DNA; každá změna rozsahu zneplatní staré odpovědi. */
export function useDnaHistory(project: string | undefined, workspace: string | undefined, nodeId: string): DnaHistoryState {
  const [brief, setBrief] = useState<NodeBrief | null>(null); const [results, setResults] = useState<AcceptedResult[]>([]); const [messages, setMessages] = useState<Message[]>([]);
  const [cursors, setCursors] = useState<HistoryCursors>({ results: null, incoming: null, outgoing: null }); const [loading, setLoading] = useState(false); const [loadingMore, setLoadingMore] = useState(false); const [error, setError] = useState(""); const [revision, setRevision] = useState(0);
  const requests = useRef(new Set<AbortController>()); const generation = useRef(0); const live = useRef(true); const available = !!project && !!workspace;
  const read = useCallback(async <T,>(url: string, signal: AbortSignal): Promise<T> => { const response = await fetch(url, { signal }); const body = await response.json() as T & { error?: string }; if (!response.ok) throw new Error(body.error ?? `Načtení selhalo (HTTP ${response.status}).`); return body; }, []);
  const active = useCallback((request: number, abort?: AbortController) => live.current && generation.current === request && !abort?.signal.aborted, []);
  const append = useCallback((pages: { results: HistoryPage<AcceptedResult>; incoming: HistoryPage<Message>; outgoing: HistoryPage<Message> }, next: HistoryCursors) => {
    setResults(current => mergeHistoryItems(current, pageItems(pages.results))); setMessages(current => mergeHistoryItems(current, [...pageItems(pages.incoming), ...pageItems(pages.outgoing)])); setCursors(next);
  }, []);
  useEffect(() => () => { live.current = false; generation.current++; requests.current.forEach(request => request.abort()); requests.current.clear(); }, []);
  useEffect(() => {
    const request = ++generation.current; requests.current.forEach(item => item.abort()); requests.current.clear(); live.current = true;
    if (!available) { setBrief(null); setResults([]); setMessages([]); setCursors({ results: null, incoming: null, outgoing: null }); setError("Chybí projekt nebo pracovní prostor."); return; }
    const abort = new AbortController(); requests.current.add(abort); setLoading(true); setError(""); setBrief(null); setResults([]); setMessages([]); setCursors({ results: null, incoming: null, outgoing: null });
    const scope = query({ project: project!, workspace: workspace!, nodeId });
    void read<BriefPage>(`/api/desktop-v3/node-brief?${scope}`, abort.signal).then(value => {
      if (!active(request, abort)) return; const communication = (value.communication ?? {}) as Record<string, HistoryPage<Message>>; const pages = { results: value.resultHistory ?? {}, incoming: communication.incoming ?? {}, outgoing: communication.outgoing ?? {} }; const next = advanceHistoryCursors({ results: null, incoming: null, outgoing: null }, pages); setBrief(value); setResults(pageItems(pages.results)); setMessages(mergeHistoryItems(pageItems(pages.incoming), pageItems(pages.outgoing))); setCursors(next);
    }).catch(reason => { if (active(request, abort)) setError(errorText(reason)); }).finally(() => { requests.current.delete(abort); if (active(request, abort)) setLoading(false); });
    return () => abort.abort();
  }, [active, available, nodeId, project, read, revision, workspace]);
  const fetchPages = useCallback(async (current: HistoryCursors, request: number) => {
    const abort = new AbortController(); requests.current.add(abort); const scope = { project: project!, workspace: workspace!, nodeId };
    try {
      const [resultPage, incoming, outgoing] = await Promise.all([
        current.results === null ? Promise.resolve({} as HistoryPage<AcceptedResult>) : read<HistoryPage<AcceptedResult>>(`/api/desktop-v3/agent-results?${query({ ...scope, before: String(current.results) })}`, abort.signal),
        current.incoming === null ? Promise.resolve({} as HistoryPage<Message>) : read<HistoryPage<Message>>(`/api/desktop-v3/agent-messages?${query({ ...scope, direction: "incoming", before: current.incoming })}`, abort.signal),
        current.outgoing === null ? Promise.resolve({} as HistoryPage<Message>) : read<HistoryPage<Message>>(`/api/desktop-v3/agent-messages?${query({ ...scope, direction: "outgoing", before: current.outgoing })}`, abort.signal),
      ]);
      if (!active(request, abort)) return null; const pages = { results: resultPage, incoming, outgoing }; return { pages, next: advanceHistoryCursors(current, pages) };
    } finally { requests.current.delete(abort); }
  }, [active, nodeId, project, read, workspace]);
  const loadMore = useCallback(async () => {
    if (!available || loadingMore || (cursors.results === null && cursors.incoming === null && cursors.outgoing === null)) return; const request = generation.current; setLoadingMore(true); setError("");
    try { const loaded = await fetchPages(cursors, request); if (loaded && active(request)) append(loaded.pages, loaded.next); } catch (reason) { if (active(request)) setError(errorText(reason)); } finally { if (active(request)) setLoadingMore(false); }
  }, [active, append, available, cursors, fetchPages, loadingMore]);
  const loadAll = useCallback(async () => {
    if (!available || loadingMore || (cursors.results === null && cursors.incoming === null && cursors.outgoing === null)) return; const request = generation.current; setLoadingMore(true); setError("");
    try { await drainHistoryPages(cursors, async current => {
      const loaded = await fetchPages(current, request);
      return loaded ? { ...loaded, cursor: loaded.next, next: Object.values(loaded.next).every(value => value === null) ? null : loaded.next } : null;
    }, loaded => append(loaded.pages, loaded.cursor), () => active(request)); } catch (reason) { if (active(request)) setError(errorText(reason)); } finally { if (active(request)) setLoadingMore(false); }
  }, [active, append, available, cursors, fetchPages, loadingMore]);
  return { brief, results, messages, before: cursors.results, loading, loadingMore, error, partial: cursors.results !== null || cursors.incoming !== null || cursors.outgoing !== null, loadMore, loadAll, reload: () => { generation.current++; setRevision(value => value + 1); } };
}
