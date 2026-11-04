// Vazba okna Pletor na React a síť: stav konverzace, srdce a eskalací jednoho prostoru se načítá
// sdíleným pollerem každé 4 s, jen když je okno otevřené (ve skryté záložce poller stojí), jako panel srdce.
// Přepnutí mozku jde z nastavení (setBrain). Odeslání hned ukáže zprávu člověka, po odpovědi drží provedené akce a čas příchodu (záblesk jádra) a požádá o nové načtení. Volá ho jen PletorWindow.
import { useCallback, useEffect, useRef, useState } from "react";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { CLAUDE_BRAIN, fetchPletorState, sendPletorMessage, setPletorBrain, type PletorAction, type PletorBrain, type PletorState } from "./pletor-client";

const POLL_MS = 4000;
const EMPTY: PletorState = { messages: [], heart: null, escalations: [], brain: CLAUDE_BRAIN };
const messageOf = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function usePletor(open: boolean, project: string, workspace: string) {
  const [state, setState] = useState<PletorState>(EMPTY);
  const [actions, setActions] = useState<PletorAction[]>([]);
  const [sending, setSending] = useState(false);
  const [failure, setFailure] = useState("");
  const [repliedAt, setRepliedAt] = useState<number | null>(null);
  const scopeKey = `${project}\n${workspace}`;
  const scopeRef = useRef(scopeKey);
  useEffect(() => {
    scopeRef.current = scopeKey;
    setState(EMPTY);
    setActions([]);
    setFailure("");
  }, [scopeKey]);

  // Výsledek jiného projektu nebo prostoru (dotaz běžel při přepnutí) se zahodí.
  const poll = usePolling(() => {
    const asked = scopeKey;
    return fetchPletorState(project, workspace)
      .then((next) => { if (scopeRef.current === asked) { setState(next); setFailure(""); } })
      .catch((error) => { if (scopeRef.current === asked) setFailure(messageOf(error)); });
  }, { intervalMs: POLL_MS, enabled: open && !!project && !!workspace, refreshKeys: [scopeKey] });

  const send = useCallback(async (text: string, voice = false) => {
    const asked = scopeKey;
    setSending(true);
    setActions([]);
    setState((current) => ({ ...current, messages: [...current.messages, { role: "human", text, at: new Date().toISOString() }] }));
    try {
      const result = await sendPletorMessage(project, workspace, text, voice);
      if (scopeRef.current !== asked) return true;
      setState((current) => ({ ...current, messages: [...current.messages, { role: "pletor", text: result.reply, at: new Date().toISOString() }] }));
      setActions(result.actions);
      setRepliedAt(Date.now());
      setFailure("");
      void poll.refresh();
      return true;
    } catch (error) {
      if (scopeRef.current === asked) setFailure(messageOf(error));
      return false;
    } finally {
      setSending(false);
    }
  }, [project, workspace, scopeKey, poll]);

  /** Přepnutí mozku z nastavení: nový stav hned ukáže řádek MOZEK, selhání (např. bez modelu Ollamy) jde do `failure`. */
  const setBrain = useCallback(async (brain: PletorBrain["brain"]) => {
    try {
      const result = await setPletorBrain(brain);
      setState((current) => ({ ...current, brain: result.brain }));
      setFailure(result.ok ? "" : result.reply);
    } catch (error) {
      setFailure(messageOf(error));
    }
  }, []);

  return { ...state, actions, sending, failure, repliedAt, send, setBrain };
}
