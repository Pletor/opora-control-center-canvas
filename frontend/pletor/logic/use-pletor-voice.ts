// Vazba hlasu Pletora (P3) na React: mikrofon → průběžný přepis → automatické odeslání stejnou cestou jako Enter,
// odpověď nahlas (když zpráva vznikla hlasem, nebo je zapnutý Hlas), v režimu Konverzace pak znovu poslech.
// Barge-in: mikrofon, Esc nebo začátek řeči čtení okamžitě utne. Volá ho jen PletorWindow, takže hlas přežije HUD ↔ okno.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PletorMessage } from "./pletor-client";
import type { VoicePhase } from "./hud-palette";
import { createVoiceInput, openMicLevel, voiceError, type MicLevel } from "./voice-input";
import { chosenVoice, createPiperOutput, fetchVoices, NO_VOICES } from "./tts-piper";
import { createVoiceOutput, speechLevel } from "./voice-output";
import { readVoicePrefs, writeVoicePrefs, type VoicePrefs } from "./voice-prefs";

type Talk = { messages: PletorMessage[]; repliedAt: number | null; send: (text: string, voice?: boolean) => Promise<boolean> };

export function usePletorVoice(talk: Talk, open: boolean) {
  const input = useMemo(() => createVoiceInput(), []);
  const [prefs, setPrefsState] = useState(readVoicePrefs);
  const [voices, setVoices] = useState(NO_VOICES);
  const chosen = chosenVoice(prefs.ttsVoice, voices);
  const [phase, setPhase] = useState<VoicePhase>("idle");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(false);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const live = useRef({ talk, prefs, open, chosen });
  live.current = { talk, prefs, open, chosen };
  // Piper (P3b), když je zvolený stažený hlas; jinak a při chybě serveru prohlížečová syntéza.
  const output = useMemo(() => createPiperOutput(createVoiceOutput(), () => live.current.chosen), []);
  // Seznam hlasů při otevření; backend přitom načte výchozí hlas do paměti, aby první odpověď nečekala.
  useEffect(() => { if (open) void fetchVoices().then(setVoices); }, [open]);
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
  useEffect(() => {
    if (talk.repliedAt === null || phaseRef.current === "listening") return;
    const spoken = voiceTurn.current;
    voiceTurn.current = false;
    const { prefs: chosen, open: visible, talk: now } = live.current;
    const again = () => { if (spoken && live.current.prefs.conversation && live.current.open) listen(); };
    const reply = [...now.messages].reverse().find((message) => message.role === "pletor");
    if (!visible || !reply || !(spoken || chosen.voice) || !output.supported) { again(); return; }
    setPhase("speaking");
    output.speak(reply.text, {
      onBoundary: () => { boundaryAt.current = performance.now(); },
      onEnd: () => { setPhase("idle"); again(); },
    });
  }, [talk.repliedAt, output, listen]);

  // Esc při poslechu nebo čtení jen utne hlas (HUD se kvůli tomu nezavře, viz `voiceBusy` v PletorHud).
  useEffect(() => {
    if (phase === "idle") return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.isComposing) return;
      event.preventDefault();
      event.stopPropagation();
      stop();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [phase, stop]);

  useEffect(() => { if (!open) stop(); }, [open, stop]);
  useEffect(() => () => { input.stop(); output.stop(); mic.current?.close(); }, [input, output]);

  /** Amplituda jádra HUD: mikrofon (nebo syntetická vlna, když AnalyserNode není), při čtení hlasitost Piperu,
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

  /** Mikrofon: při poslechu stop, jinak poslouchej (čtení odpovědi se tím utne). */
  const toggle = useCallback(() => (phaseRef.current === "listening" ? stop() : listen()), [stop, listen]);

  return { supported: input.supported, phase, interim, error, blocked, prefs, setPrefs, toggle, level, voices: voices.available, chosen };
}
