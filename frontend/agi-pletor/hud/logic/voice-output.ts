/**
 * Hlasový výstup Pletora (P3): prohlížečová syntéza řeči česky. Rozhraní `VoiceOutput` je stejně malé jako
 * `VoiceInput`, aby ho v P3b šlo vyměnit za lokální TTS přes backend.
 */

export type VoiceOutputEvents = {
  /** Hranice slova: jádro HUD pulzne. */
  onBoundary?: () => void;
  /** Domluveno (ne po `stop`, ten je barge-in a nic dalšího se nespouští). */
  onEnd: () => void;
};
export type VoiceOutput = { supported: boolean; speak: (text: string, events: VoiceOutputEvents) => void; stop: () => void };

type Voice = { name: string; lang: string };
type Utterance = {
  text: string; lang: string; voice: Voice | null; rate: number; pitch: number;
  onboundary: (() => void) | null; onend: (() => void) | null; onerror: (() => void) | null;
};
type Synth = { speak: (utterance: Utterance) => void; cancel: () => void; getVoices: () => Voice[] };
export type UtteranceCtor = new (text: string) => Utterance;

const MAX_CHUNK = 180;

/** Text, který jde číst nahlas: bez markdownu, odkazů, emoji a závorek s ID (`(#330)`, `(t-12ab)`); „5.5“ zůstane. */
export function speakable(text: string): string {
  return text
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/https?:\/\/\S*[^\s.,!?…]/g, " ")
    .replace(/\s*\(#?[\w-]*\d[\w-]*\)/g, "")
    .replace(/\p{Extended_Pictographic}️?/gu, " ")
    .replace(/[*_#`>|~]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Odpověď → věty k přečtení. Chrome po ~15 s jedné promluvy zamlkne a Piper začne hrát dřív po krátké větě,
 *  proto věta po větě a dlouhá věta po slovech. */
export function splitSentences(text: string, max = MAX_CHUNK): string[] {
  const clean = speakable(text);
  const out: string[] = [];
  for (const sentence of clean.split(/(?<=[.!?…])\s+/)) {
    if (sentence.length <= max) { if (sentence) out.push(sentence); continue; }
    let chunk = "";
    for (const word of sentence.split(" ")) {
      if (chunk && chunk.length + 1 + word.length > max) { out.push(chunk); chunk = word; } else chunk = chunk ? `${chunk} ${word}` : word;
    }
    if (chunk) out.push(chunk);
  }
  return out;
}

/** Český hlas: nejdřív `cs*` od Google/Microsoft (nebo mužský), jinak první `cs*`, jinak výchozí prohlížeče (`null`). */
export function pickVoice<V extends Voice>(voices: V[]): V | null {
  const czech = voices.filter((voice) => voice.lang.toLowerCase().startsWith("cs"));
  return czech.find((voice) => /google|microsoft|male/i.test(voice.name)) ?? czech[0] ?? null;
}

/** Amplituda jádra při mluvení: záblesk na hranici slova doznívá 300 ms, pod ním tiché vlnění (ms). */
export function speechLevel(now: number, boundaryAt: number): number {
  return Math.max(0, 1 - (now - boundaryAt) / 300) * 0.6 + Math.abs(Math.sin(now / 110)) * 0.15;
}

const scope = globalThis as unknown as { speechSynthesis?: Synth; SpeechSynthesisUtterance?: UtteranceCtor };
const globalSynth = () => scope.speechSynthesis ?? null;
const globalUtterance = () => scope.SpeechSynthesisUtterance ?? null;

export function createVoiceOutput(synth: Synth | null = globalSynth(), Ctor: UtteranceCtor | null = globalUtterance()): VoiceOutput {
  let token = 0;
  synth?.getVoices(); // první volání v Chrome spustí načtení hlasů
  const stop = () => {
    token++;
    try { synth?.cancel(); } catch { /* nic nemluví */ }
  };
  const speak = (text: string, events: VoiceOutputEvents) => {
    stop();
    if (!synth || !Ctor) { events.onEnd(); return; }
    const mine = token;
    const queue = splitSentences(text);
    const next = () => {
      if (mine !== token) return;
      const sentence = queue.shift();
      if (!sentence) { events.onEnd(); return; }
      const utterance = new Ctor(sentence);
      const voice = pickVoice(synth.getVoices());
      utterance.lang = voice?.lang ?? "cs-CZ";
      utterance.voice = voice;
      utterance.rate = 1.02;
      utterance.pitch = 0.9;
      utterance.onboundary = () => { if (mine === token) events.onBoundary?.(); };
      // Chyba jedné věty (i „interrupted“ po cancel) neshodí čtení: další věta, nebo konec, když přišel stop.
      // Prohlížeč může poslat error i end téže věty; dál se jde jen jednou.
      let done = false;
      const finish = () => { if (!done) { done = true; next(); } };
      utterance.onend = finish;
      utterance.onerror = finish;
      try { synth.speak(utterance); } catch { finish(); }
    };
    next();
  };
  return { supported: !!synth && !!Ctor, speak, stop };
}
