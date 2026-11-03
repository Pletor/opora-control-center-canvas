// Vazba kanálu Srdce na React a síť: eskalace, tickety práce, stav srdce jednoho pracovního prostoru
// a při běžící dávce její zápisy v záznamu činnosti (`liveSteps`, od `current.startedAt`).
// Načítá se sdíleným pollerem každé 4 s, jen když je kanál vidět (ve skryté záložce poller stojí).
// Odpověď na eskalaci a zpráva srdci po úspěchu hned požádají o nové načtení. Volá ho jen HeartChannel.
import { useCallback, useEffect, useRef, useState } from "react";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import {
  answerEscalation,
  fetchEscalations,
  fetchHeartStatus,
  fetchHeartSteps,
  fetchTickets,
  sendHeartMessage,
  type Escalation,
  type HeartStatus,
  type WorkTicket,
} from "./heart-api";
import { heartStepsQuery } from "./heart-live";
import type { ActivityEntry } from "@/editor/canvas/activity-log/logic/activity-log";

const POLL_MS = 4000;

const messageOf = (error: unknown) => (error instanceof Error ? error.message : String(error));

export type HeartChannelData = {
  escalations: Escalation[];
  tickets: WorkTicket[];
  status: HeartStatus | null;
  /** Zápisy srdce běžící dávky, nejnovější první; bez dávky prázdné. */
  liveSteps: ActivityEntry[];
  loaded: boolean;
  failure: string;
  setFailure: (text: string) => void;
  answer: (ticketId: string, text: string) => Promise<boolean>;
  send: (text: string) => Promise<boolean>;
};

export function useHeartChannel(active: boolean, project: string, workspace: string): HeartChannelData {
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [tickets, setTickets] = useState<WorkTicket[]>([]);
  const [status, setStatus] = useState<HeartStatus | null>(null);
  const [liveSteps, setLiveSteps] = useState<ActivityEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [failure, setFailure] = useState("");
  const scopeKey = `${project}\n${workspace}`;
  const scopeRef = useRef(scopeKey);
  useEffect(() => {
    scopeRef.current = scopeKey;
    setEscalations([]);
    setTickets([]);
    setStatus(null);
    setLiveSteps([]);
    setLoaded(false);
  }, [scopeKey]);

  // Výsledek jiného projektu nebo prostoru (dotaz běžel při přepnutí) se zahodí.
  const poll = usePolling(() => {
    const asked = scopeKey;
    return Promise.all([fetchEscalations(project, workspace), fetchTickets(project, workspace), fetchHeartStatus(project)])
      .then(async ([nextEscalations, nextTickets, nextStatus]) => {
        const since = nextStatus.current?.startedAt;
        const nextSteps = since ? await fetchHeartSteps(heartStepsQuery(project, { since })) : [];
        if (scopeRef.current !== asked) return;
        setEscalations(nextEscalations);
        setTickets(nextTickets);
        setStatus(nextStatus);
        setLiveSteps(nextSteps);
        setLoaded(true);
      })
      .catch((error) => { if (scopeRef.current === asked) setFailure(messageOf(error)); });
  }, { intervalMs: POLL_MS, enabled: active && !!project && !!workspace, refreshKeys: [scopeKey] });

  const answer = useCallback(async (ticketId: string, text: string) => {
    try {
      await answerEscalation(project, ticketId, text);
      setEscalations((list) => list.filter((item) => item.ticketId !== ticketId));
      void poll.refresh();
      return true;
    } catch (error) {
      setFailure(messageOf(error));
      return false;
    }
  }, [project, poll]);

  const send = useCallback(async (text: string) => {
    try {
      await sendHeartMessage(project, workspace, text);
      void poll.refresh();
      return true;
    } catch (error) {
      setFailure(messageOf(error));
      return false;
    }
  }, [project, workspace, poll]);

  return { escalations, tickets, status, liveSteps, loaded, failure, setFailure, answer, send };
}
