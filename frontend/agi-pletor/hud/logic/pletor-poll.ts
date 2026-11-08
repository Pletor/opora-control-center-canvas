// Vazba okna Pletor na React a síť: stav konverzace, srdce a eskalací jednoho prostoru se načítá
// sdíleným pollerem, jen když je Pletor aktivní (ve skryté záložce poller stojí). Když je vidět HUD nebo okno
// (`heartOn`), týž poller čte i plný stav srdce pro panel Srdce, každé 3 s během práce srdce, jinak každých 5 s.
// Přepnutí mozku jde z nastavení (setBrain). Odeslání hned ukáže zprávu člověka, po odpovědi drží provedené akce a čas příchodu (záblesk jádra) a požádá o nové načtení. Volá ho jen PletorWindow.
import { useCallback, useEffect, useRef, useState } from "react";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { fetchHeartStatus, type HeartStatus } from "@/layout/heart-channel/logic/heart-api";
import { pollMs } from "@/agi-pletor/hud-heart/logic/heart-panel";
import { CLAUDE_BRAIN, fetchPletorQuestion, fetchPletorState, sendPletorMessage, sendPletorMessageStream, setPletorBrain, type PletorAction, type PletorBrain, type PletorState } from "./pletor-client";

const EMPTY: PletorState = { messages: [], heart: null, escalations: [], brain: CLAUDE_BRAIN };
/** `heartStatus`: `undefined` = nenačteno nebo panel skrytý, `null` = dotaz na stav srdce selhal.
 *  `loaded`: rozhovor tohoto prostoru už jednou přišel ze serveru (hlas pak pozná novou proaktivní zprávu). */
type Polled = PletorState & { question: string; answered: boolean; heartStatus?: HeartStatus | null; loaded: boolean };
const FRESH: Polled = { ...EMPTY, question: "", answered: false, loaded: false };
const messageOf = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function usePletor(open: boolean, project: string, workspace: string, heartOn = false) {
  const [state, setState] = useState<Polled>(FRESH);
  const heart = useRef<HeartStatus | null | undefined>(undefined);
  const [actions, setActions] = useState<PletorAction[]>([]);
  const [sending, setSending] = useState(false);
  const [failure, setFailure] = useState("");
  const [repliedAt, setRepliedAt] = useState<number | null>(null);
  const scopeKey = `${project}\n${workspace}`;
  const scopeRef = useRef(scopeKey);
  useEffect(() => {
    scopeRef.current = scopeKey;
    setState(FRESH);
    heart.current = undefined;
    setActions([]);
    setFailure("");
  }, [scopeKey]);

  // Výsledek jiného projektu nebo prostoru (dotaz běžel při přepnutí) se zahodí.
  const poll = usePolling(() => {
    const asked = scopeKey;
    // Řádek otázky a stav srdce jsou doplněk: jejich výpadek rozhovor neshodí; otázka zmizí, panel řekne „nedostupný“.
    const status = heartOn ? fetchHeartStatus(project).catch(() => null) : Promise.resolve(undefined);
    return Promise.all([fetchPletorState(project, workspace), fetchPletorQuestion(project).catch(() => ({ text: "", answered: false })), status])
      .then(([next, question, heartStatus]) => {
        if (scopeRef.current !== asked) return;
        heart.current = heartStatus;
        setState({ ...next, question: question.text, answered: question.answered, heartStatus, loaded: true });
        setFailure("");
      })
      .catch((error) => { if (scopeRef.current === asked) setFailure(messageOf(error)); });
  }, { intervalMs: () => pollMs(heart.current), enabled: open && !!project && !!workspace, refreshKeys: [scopeKey, heartOn] });

  /** Hlasová zpráva jde proudem (`onDelta` dostává kousky odpovědi ke čtení), ostatní najednou; zápis do rozhovoru až po `done`. */
  const send = useCallback(async (text: string, voice = false, onDelta: (text: string) => void = () => undefined) => {
    const asked = scopeKey;
    setSending(true);
    setActions([]);
    setState((current) => ({ ...current, messages: [...current.messages, { role: "human", text, at: new Date().toISOString() }] }));
    try {
      const result = voice
        ? await sendPletorMessageStream(project, workspace, text, voice, onDelta)
        : await sendPletorMessage(project, workspace, text, voice);
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
  const setBrain = useCallback(async (brain: PletorBrain["brain"], model?: string, effort?: string) => {
    try {
      const result = await setPletorBrain(brain, model, effort);
      setState((current) => ({ ...current, brain: result.brain }));
      setFailure(result.ok ? "" : result.reply);
    } catch (error) {
      setFailure(messageOf(error));
    }
  }, []);

  return { ...state, actions, sending, failure, repliedAt, send, setBrain };
}
