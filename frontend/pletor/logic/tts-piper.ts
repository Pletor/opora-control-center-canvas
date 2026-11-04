/**
 * Hlas Pletora z Piperu přes backend (P3b): české hlasy Jirka a Kasandra, lokálně a zdarma. Stejné rozhraní
 * `VoiceOutput` jako prohlížečová syntéza, která je zálohou (žádný stažený hlas, volba Prohlížeč, chyba serveru).
 * Rychlost: věty se syntetizují souběžně (nejvýš 2 v letu), první hraje hned, další navazují bez pauzy v AudioContextu.
 */
import { api } from "@/shared/types/logic/types";
import { splitSentences, type VoiceOutput, type VoiceOutputEvents } from "./voice-output";

export type PiperVoice = { id: string; label: string; gender: "male" | "female" };
export type PiperVoices = { available: PiperVoice[]; default: string | null };
export type PiperOutput = VoiceOutput & { level: () => number | null };
type Speech = (text: string, voice: string, signal: AbortSignal) => Promise<ArrayBuffer>;

export const NO_VOICES: PiperVoices = { available: [], default: null };
export const BROWSER_VOICE = "browser";
const IN_FLIGHT = 2;

export function parseVoices(value: unknown): PiperVoices {
  const raw = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
  const available = (Array.isArray(raw.available) ? raw.available : []).filter((voice): voice is PiperVoice =>
    !!voice && typeof voice.id === "string" && typeof voice.label === "string");
  const fallback = available.some((voice) => voice.id === raw.default) ? (raw.default as string) : null;
  return { available, default: fallback };
}

/** Stažené hlasy; nedostupný server = žádné, čte prohlížeč. */
export const fetchVoices = () => api<unknown>("/api/pletor/voices").then(parseVoices, () => NO_VOICES);

/** Hlas Piperu ke čtení, nebo `null` = prohlížeč. Bez volby (nebo se smazaným hlasem) výchozí stažený. */
export function chosenVoice(pref: string | null, voices: PiperVoices): string | null {
  if (pref === BROWSER_VOICE) return null;
  return voices.available.some((voice) => voice.id === pref) ? pref : voices.default;
}

// shortcut: cookie člověka už existuje (odpověď přišla přes api POST); po restartu serveru 428 → čte prohlížeč, dokud nepřijde další zpráva.
export const fetchSpeech: Speech = async (text, voice, signal) => {
  const response = await fetch("/api/pletor/tts", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, voice }), signal,
  });
  if (!response.ok) throw new Error(`Hlas Pletora: HTTP ${response.status}`);
  return response.arrayBuffer();
};

const browserAudio = () => {
  try {
    return typeof AudioContext === "function" ? new AudioContext() : null;
  } catch {
    return null;
  }
};

export function createPiperOutput(fallback: VoiceOutput, voice: () => string | null, speech: Speech = fetchSpeech,
  makeAudio: () => AudioContext | null = browserAudio): PiperOutput {
  let token = 0;
  let abort: AbortController | null = null;
  let playing: AudioBufferSourceNode[] = [];
  let audio: { context: AudioContext; analyser: AnalyserNode; data: Uint8Array<ArrayBuffer> } | null = null;

  const context = () => {
    if (audio) return audio;
    const made = makeAudio();
    if (!made) return null;
    const analyser = made.createAnalyser();
    analyser.fftSize = 256;
    analyser.connect(made.destination);
    audio = { context: made, analyser, data: new Uint8Array(analyser.fftSize) };
    return audio;
  };

  const stop = () => {
    token++;
    abort?.abort();
    abort = null;
    for (const source of playing) {
      source.onended = null;
      try { source.stop(); } catch { /* ještě nehrál */ }
    }
    playing = [];
    fallback.stop();
  };

  const speak = (text: string, events: VoiceOutputEvents) => {
    stop();
    const id = voice();
    const sound = id ? context() : null;
    if (!id || !sound) { fallback.speak(text, events); return; }
    const sentences = splitSentences(text);
    if (!sentences.length) { events.onEnd(); return; }
    const { context: ctx, analyser } = sound;
    const mine = token;
    const controller = new AbortController();
    abort = controller;
    void ctx.resume().catch(() => undefined);
    const started = performance.now();
    const load = (sentence: string) => {
      const buffer = speech(sentence, id, controller.signal).then((data) => ctx.decodeAudioData(data));
      buffer.catch(() => undefined); // zrušené dopředu stažené věty nejsou chyba
      return buffer;
    };
    const queue = sentences.slice(0, IN_FLIGHT).map(load);
    void (async () => {
      let end = 0;
      for (let i = 0; i < sentences.length; i++) {
        let buffer: AudioBuffer;
        try {
          buffer = await queue[i];
          if (ctx.state === "suspended") throw new Error("AudioContext nesmí hrát");
        } catch {
          if (mine !== token) return;
          // Hlas chybí (404) nebo server neodpověděl: zbytek dočte prohlížeč, až dohraje, co už zní.
          const rest = sentences.slice(i).join(" ");
          setTimeout(() => { if (mine === token) fallback.speak(rest, events); }, Math.max(0, end - ctx.currentTime) * 1000);
          return;
        }
        if (mine !== token) return;
        if (queue.length < sentences.length) queue.push(load(sentences[queue.length]));
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(analyser);
        const when = Math.max(ctx.currentTime, end);
        source.start(when);
        end = when + buffer.duration;
        playing.push(source);
        if (i === 0) console.debug(`Pletor TTFA ${Math.round(performance.now() - started)} ms (Piper ${id})`);
        if (i === sentences.length - 1) source.onended = () => { if (mine === token) { playing = []; events.onEnd(); } };
      }
    })();
  };

  /** Hlasitost právě hraného zvuku (RMS) pro jádro HUD; mimo Piper `null` a hook vezme syntetický puls. */
  const level = () => {
    if (!audio || !playing.length) return null;
    audio.analyser.getByteTimeDomainData(audio.data);
    let sum = 0;
    for (const value of audio.data) sum += ((value - 128) / 128) ** 2;
    return Math.min(1, Math.sqrt(sum / audio.data.length) * 4);
  };

  return { supported: fallback.supported || typeof AudioContext === "function", speak, stop, level };
}
