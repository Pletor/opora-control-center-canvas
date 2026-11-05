// Trvalý poslech Pletora (přepínač Poslech): mikrofon běží, dokud ho člověk nevypne, a každá smysluplná věta
// (síto wake-word.ts) jde Pletorovi stejnou cestou jako dosud. Smyčka nad tímtéž `VoiceInput`, který má
// usePletorVoice, takže v aplikaci je jen jeden poslech. Prohlížeč poslech sám ukončuje (ticho, síť), proto
// se po konci znovu spustí; selhání se opakuje s rostoucí prodlevou a po MAX_RESTARTS se smyčka vzdá.
// Při přemýšlení a čtení odpovědi je poslech pozastavený (mikrofon vedle reproduktorů by slyšel sám sebe).
import { useEffect, useMemo, useRef } from "react";
import { readListenPrefs } from "./listen-prefs";
import { voiceError, type VoiceInput } from "./voice-input";
import { heardCommand, type Heard } from "./wake-word";

/** Prodleva obnovení po dohrání odpovědi, aby mikrofon nechytil dozvuk reproduktoru (ms). */
export const RESUME_MS = 400;
/** Běžný konec poslechu (ticho) se obnoví hned; selhání s prodlevou 0,5 → 1 → 2 … s, nejvýš 8 s. */
export const RESTART_MS = 250;
export const MAX_RESTARTS = 6;
/** Poslech kratší než tohle bez jediného slova je selhání, ne ticho (prohlížeč končí hned po startu). */
export const MIN_RUN_MS = 1000;
export const GAVE_UP = "Poslech se opakovaně přerušil. Zkontroluj mikrofon a zapni Poslech znovu.";

/** Další pokus po konci poslechu, nebo `null` = vzdát (příliš mnoho selhání po sobě). */
export function restartPlan(attempt: number, failed: boolean): { attempt: number; delay: number } | null {
  if (!failed) return { attempt: 0, delay: RESTART_MS };
  if (attempt >= MAX_RESTARTS) return null;
  return { attempt: attempt + 1, delay: Math.min(8000, 500 * 2 ** attempt) };
}

export type ListenLoopEvents = {
  /** Prohlížeč právě poslouchá (`true`), nebo je poslech pozastavený / vypnutý. */
  onListening: (on: boolean) => void;
  onInterim: (text: string) => void;
  /** Věta prošla sítem; smyčka je už pozastavená a obnoví ji `resume` (po odpovědi nebo selhání odeslání). */
  onCommand: (text: string) => void;
  /** Nepovolený mikrofon nebo vzdání; smyčka je vypnutá a rodič vrátí přepínač na false s touto hláškou. */
  onFail: (message: string) => void;
};
export type ListenLoop = { start: () => void; stop: () => void; pause: () => void; resume: () => void; active: () => boolean };

export function createListenLoop(input: VoiceInput, events: ListenLoopEvents, wakeOnly: () => boolean = () => readListenPrefs().wakeOnly): ListenLoop {
  let on = false;
  let paused = false;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let last: Heard | null = null;

  const halt = () => {
    clearTimeout(timer);
    input.stop();
    events.onListening(false);
    events.onInterim("");
  };
  const fail = (message: string) => { on = false; halt(); events.onFail(message); };

  const run = () => {
    clearTimeout(timer);
    if (!on || paused) return;
    const startedAt = Date.now();
    let heardAny = false;
    let failed = false;
    let fatal = "";
    events.onListening(true);
    input.start({
      onSpeech: () => { heardAny = true; },
      onInterim: (text) => { heardAny = true; events.onInterim(text); },
      onFinal: (text) => {
        if (!on || paused) return;
        heardAny = true;
        const now = Date.now();
        const command = heardCommand(text, { wakeOnly: wakeOnly(), last, now });
        last = { text, at: now };
        events.onInterim("");
        if (!command) return;
        paused = true;
        halt();
        events.onCommand(command);
      },
      onError: (code) => {
        const problem = voiceError(code);
        if (problem?.blocked) fatal = problem.text;
        else if (problem) failed = true;
      },
      onEnd: () => {
        events.onListening(false);
        events.onInterim("");
        if (!on || paused) return;
        if (fatal) { fail(fatal); return; }
        const plan = restartPlan(attempt, failed || (!heardAny && Date.now() - startedAt < MIN_RUN_MS));
        if (!plan) { fail(GAVE_UP); return; }
        attempt = plan.attempt;
        timer = setTimeout(run, plan.delay);
      },
    }, { continuous: true });
  };

  return {
    start: () => { on = true; paused = false; attempt = 0; run(); },
    stop: () => { if (!on) return; on = false; paused = false; halt(); },
    pause: () => { if (!on || paused) return; paused = true; halt(); },
    resume: () => {
      if (!on || !paused) return;
      paused = false;
      clearTimeout(timer);
      timer = setTimeout(run, RESUME_MS);
    },
    active: () => on,
  };
}

/** Smyčka pro React: zapne se a vypne podle přepínače, handlery čte vždy čerstvé. Volá ji jen usePletorVoice. */
export function usePletorListen(input: VoiceInput, on: boolean, events: ListenLoopEvents): ListenLoop {
  const live = useRef(events);
  live.current = events;
  const loop = useMemo(() => createListenLoop(input, {
    onListening: (value) => live.current.onListening(value),
    onInterim: (text) => live.current.onInterim(text),
    onCommand: (text) => live.current.onCommand(text),
    onFail: (message) => live.current.onFail(message),
  }), [input]);
  useEffect(() => {
    if (on) loop.start(); // bez rozpoznávání řeči skončí hned chybou not-supported → onFail
    else loop.stop();
    return () => loop.stop();
  }, [on, input, loop]);
  return loop;
}
