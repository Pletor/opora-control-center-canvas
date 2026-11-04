// Vazba hlasu Pletora (P3) na React: mikrofon → průběžný přepis → automatické odeslání stejnou cestou jako Enter,
// odpověď nahlas (když zpráva vznikla hlasem, nebo je zapnutý Hlas), v režimu Konverzace pak znovu poslech.
// Barge-in: mikrofon, Esc nebo začátek řeči čtení okamžitě utne. Volá ho jen PletorWindow, takže hlas přežije HUD ↔ okno.
// Přepínač Poslech (`listenSwitch.on`) přidá trvalý poslech (usePletorListen) nad tímtéž vstupem: při čtení odpovědi je
// pozastavený a čtení utne jen klik, Esc nebo vypnutí; vypnutí zastaví vše a uvolní mikrofon.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PletorMessage } from "./pletor-client";
import type { VoicePhase } from "./hud-palette";
import { createVoiceInput, openMicLevel, voiceError, type MicLevel } from "./voice-input";
import { createServerOutput } from "./tts-output";
import { chosenVoice, fetchVoices, voiceChain, type ServerVoice } from "./tts-voices";
import { createVoiceOutput, speechLevel } from "./voice-output";
import { readVoicePrefs, writeVoicePrefs, type VoicePrefs } from "./voice-prefs";
import { usePletorListen } from "./use-pletor-listen";

type Talk = { messages: PletorMessage[]; repliedAt: number | null; send: (text: string, voice?: boolean) => Promise<boolean> };
type Listen = { on: boolean; onFail: (message: string) => void };
const NO_LISTEN: Listen = { on: false, onFail: () => undefined };

export function usePletorVoice(talk: Talk, open: boolean, listenSwitch: Listen = NO_LISTEN) {
  const input = useMemo(() => createVoiceInput(), []);
  const [prefs, setPrefsState] = useState(readVoicePrefs);
  const [voices, setVoices] = useState<ServerVoice[]>([]);
  const chosen = chosenVoice(prefs.ttsVoice, voices);
  const chain = useMemo(() => voiceChain(chosen, voices), [chosen, voices]);
  const [phase, setPhase] = useState<VoicePhase>("idle");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(false);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const live = useRef({ talk, prefs, open, chain, listenSwitch });
  live.current = { talk, prefs, open, chain, listenSwitch };
  // Hlas serveru (XTTS / Edge / Piper) se zálohami v pořadí; bez hlasu serveru a nakonec vždy prohlížeč.
  const output = useMemo(() => createServerOutput(createVoiceOutput(), () => live.current.chain), []);
  // Seznam hlasů při otevření; backend přitom načte zvolený hlas dopředu (XTTS do GPU), aby první odpověď nečekala.
  useEffect(() => { if (open) void fetchVoices(live.current.prefs.ttsVoice).then(setVoices); }, [open]);
  const mic = useRef<MicLevel | null>(null);
  const micRun = useRef(0); // mikrofon otevřený po stopu se hned zavře
  const boundaryAt = useRef(0);
  const voiceTurn = useRef(false); // poslední odeslaná zpráva vznikla hlasem

  const closeMic = useCallback(() => {
    micRun.current++;
    mic.current?.close();
    mic.current = null;
  }, []);

  const stop = useCallback(() => {
    input.stop();
    output.stop();
    closeMic();
    setInterim("");
    setPhase("idle");
  }, [input, output, closeMic]);

  const loop = usePletorListen(input, listenSwitch.on, {
    onListening: (on) => setPhase((current) => (on ? "listening" : current === "listening" ? "idle" : current)),
    onInterim: setInterim,
    onCommand: (text) => {
      voiceTurn.current = true;
      void live.current.talk.send(text, true).then((ok) => { if (!ok) { voiceTurn.current = false; loop.resume(); } });
    },
    onFail: (message) => { setError(message); live.current.listenSwitch.onFail(message); },
  });

  // Poslech zapnutý: mikrofon pro hlasitost jádra drží otevřený celou dobu; vypnutí utne vše a uvolní ho.
  useEffect(() => {
    if (!listenSwitch.on) return;
    setError("");
    closeMic();
    const run = micRun.current;
    void openMicLevel().then((level) => { if (level && micRun.current === run) mic.current = level; else level?.close(); });
    return () => { voiceTurn.current = false; stop(); };
  }, [listenSwitch.on, stop, closeMic]);

  /** Utne čtení odpovědi; v Poslechu pak po krátké prodlevě znovu poslouchá. */
  const interrupt = useCallback(() => {
    output.stop();
    setPhase((current) => (current === "speaking" ? "idle" : current));
    loop.resume();
  }, [output, loop]);

  const listen = useCallback(() => {
    if (!input.supported) return;
    output.stop();
    closeMic();
    setError("");
    setInterim("");
    setPhase("listening");
    const run = micRun.current;
    void openMicLevel().then((level) => { if (level && micRun.current === run) mic.current = level; else level?.close(); });
    input.start({
      onSpeech: () => output.stop(),
      onInterim: setInterim,
      onFinal: (text) => {
        closeMic();
        setInterim("");
        setPhase("idle");
        voiceTurn.current = true;
        void live.current.talk.send(text, true).then((ok) => { if (!ok) voiceTurn.current = false; });
      },
      onError: (code) => {
        const problem = voiceError(code);
        if (!problem) return;
        setError(problem.text);
        if (problem.blocked) setBlocked(true);
      },
      onEnd: () => {
        closeMic();
        setInterim("");
        setPhase((current) => (current === "listening" ? "idle" : current));
      },
    });
  }, [input, output, closeMic]);

  // Odpověď přišla: nahlas jen po hlasové zprávě nebo se zapnutým Hlasem; Konverzace pak znovu poslouchá.
  // V Poslechu se mikrofon při čtení pozastaví (neslyší reproduktor) a po dohrání se obnoví.
  useEffect(() => {
    if (talk.repliedAt === null || (!loop.active() && phaseRef.current === "listening")) return;
    const spoken = voiceTurn.current;
    voiceTurn.current = false;
    const { prefs: chosen, open: visible, talk: now } = live.current;
    const again = () => {
      if (loop.active()) loop.resume();
      else if (spoken && live.current.prefs.conversation && live.current.open) listen();
    };
    const reply = [...now.messages].reverse().find((message) => message.role === "pletor");
    if (!visible || !reply || !(spoken || chosen.voice) || !output.supported) { again(); return; }
    loop.pause();
    setPhase("speaking");
    output.speak(reply.text, {
      onBoundary: () => { boundaryAt.current = performance.now(); },
      onEnd: () => { setPhase("idle"); again(); },
    });
  }, [talk.repliedAt, output, listen, loop]);

  // Esc při poslechu nebo čtení jen utne hlas (HUD se kvůli tomu nezavře, viz `voiceBusy` v PletorHud).
  // V Poslechu Esc utne jen čtení; poslech vypíná přepínač.
  const ambient = listenSwitch.on;
  useEffect(() => {
    if (phase === "idle" || (ambient && phase !== "speaking")) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.isComposing) return;
      event.preventDefault();
      event.stopPropagation();
      if (ambient) interrupt(); else stop();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [phase, ambient, stop, interrupt]);

  useEffect(() => { if (!open) stop(); }, [open, stop]);
  useEffect(() => () => { input.stop(); output.stop(); mic.current?.close(); }, [input, output]);

  /** Amplituda jádra HUD: mikrofon (nebo syntetická vlna, když AnalyserNode není), při čtení hlasitost hlasu serveru,
   *  u prohlížečového hlasu puls slov. */
  const level = useCallback((): number | null => {
    const now = performance.now();
    if (phaseRef.current === "listening") return mic.current ? mic.current.level() : 0.15 + Math.abs(Math.sin(now / 180)) * 0.2;
    if (phaseRef.current === "speaking") return output.level() ?? speechLevel(now, boundaryAt.current);
    return null;
  }, [output]);

  const setPrefs = useCallback((change: Partial<VoicePrefs>) => {
    setPrefsState((current) => {
      const next = { ...current, ...change };
      writeVoicePrefs(next);
      return next;
    });
  }, []);

  /** Mikrofon: při poslechu stop, jinak poslouchej (čtení odpovědi se tím utne). V Poslechu jen utne čtení. */
  const toggle = useCallback(() => {
    if (loop.active()) interrupt();
    else if (phaseRef.current === "listening") stop();
    else listen();
  }, [loop, interrupt, stop, listen]);

  return { supported: input.supported, phase, interim, error, blocked, prefs, setPrefs, toggle, interrupt, ambient, level, voices, chosen };
}
