import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { boardView, type Board } from "./linie-board";
import { appendJournal, journalView, type Journal } from "./linie-journal";
import { requestKey, requestsView, type HeartRequest } from "./linie-requests";
import { graphView } from "./linie-view";
import { failureText } from "./linie-work";

const POLL_MS = 10000;
const CLOCK_MS = 15000;
const JOURNAL_PAGE = 200;
export const BASE = "/api/pletor/linie";
export type Group = "branch" | "plan";

/**
 * Data Linie v jednom tiknutí: board (a týž snímek přeskládaný podle plánu, `?group=plan&snapshot=`), Git graf, deník
 * (`/journal?after=lastId`, stránky po id) a žádosti srdci (`/api/pletor/requests?open=1`). Hodiny tikají nezávisle:
 * při výpadku API stáří zdrojů i posledního čtení dál roste. `ask` zapíše žádost srdci s klíčem idempotence.
 */
export function useLinieFeed(project: string, workspace: string, group: Group) {
  const query = new URLSearchParams({ project, workspace }).toString();
  const [boardRaw, setBoardRaw] = useState<unknown>(null);
  const [planRaw, setPlanRaw] = useState<unknown>(null);
  const [graphRaw, setGraphRaw] = useState<unknown>(null);
  const [journal, setJournal] = useState<Journal>({ events: [], lastId: 0 });
  const [requests, setRequests] = useState<HeartRequest[] | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [lastSuccessAt, setLastSuccessAt] = useState<number | null>(null);
  const [boardError, setBoardError] = useState("");
  const [error, setError] = useState("");
  const live = useRef({ group, journal });
  live.current = { group, journal };
  const fail = (failure: unknown) => setError(failureText(failure, "Načtení selhalo."));

  // Pohled podle plánu je týž snímek; když už snímek v paměti serveru není (404), sestaví se znovu bez něj.
  const loadPlan = async (snapshot: string) => {
    const url = (id: string) => `${BASE}/board?${query}&group=plan${id ? `&snapshot=${encodeURIComponent(id)}` : ""}`;
    try { setPlanRaw(await api<unknown>(url(snapshot))); } catch (failure) {
      if (!(snapshot && failure instanceof ApiError && failure.status === 404)) throw failure;
      setPlanRaw(await api<unknown>(url("")));
    }
  };
  const loadBoard = async () => {
    const next = await api<unknown>(`${BASE}/board?${query}`);
    const at = Date.now();
    setBoardRaw(next); setNow(at); setLastSuccessAt(at); setBoardError(""); setError("");
    if (live.current.group === "plan") await loadPlan(boardView(next).snapshot?.id ?? "");
  };
  const loadJournal = () => api<unknown>(`${BASE}/journal?${query}&after=${live.current.journal.lastId}&limit=${JOURNAL_PAGE}`)
    .then((raw) => setJournal((known) => appendJournal(known, journalView(raw))));
  const loadRequests = () => api<unknown>(`/api/pletor/requests?project=${encodeURIComponent(project)}&open=1`).then((raw) => setRequests(requestsView(raw)));

  const poll = usePolling(() => Promise.all([
    loadBoard().catch((failure: unknown) => { setBoardError(failureText(failure, "Načtení selhalo.")); fail(failure); }),
    api<unknown>(`${BASE}/graph?${query}`).then(setGraphRaw, fail),
    loadJournal().catch(fail),
    loadRequests().catch(() => setRequests(null)), // bez žádostí fronta Pletora hlásí „nedostupné“, nic nevymýšlí
  ]), { intervalMs: POLL_MS, refreshKeys: [query, group] });
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), CLOCK_MS);
    return () => clearInterval(id);
  }, []);

  const nonce = useRef(crypto.randomUUID?.() ?? String(Date.now()));
  /** Žádost srdci: hned vznikne jen „žádost přijata“; další kroky přidá služba s důkazem. Vrací text pro člověka. */
  const ask = (text: string) => api(`/api/pletor/requests?project=${encodeURIComponent(project)}`, { text: text.trim(), idempotencyKey: requestKey(text, `${nonce.current}-${Date.now()}`) })
    .then(() => "Žádost přijata – každý další krok se objeví až po potvrzení.", (failure: unknown) => failureText(failure)).finally(() => void poll.refresh());

  const branchBoard: Board = boardView(boardRaw);
  const board = group === "plan" && planRaw ? boardView(planRaw) : branchBoard;
  return { query, board, branchBoard, view: graphView(graphRaw), journal, requests, now, lastSuccessAt, boardError, error, setError, refresh: poll.refresh, ask };
}
