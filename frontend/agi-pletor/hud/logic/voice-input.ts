/**
 * Hlasový vstup Pletora (P3): prohlížečové rozpoznávání řeči (cs-CZ), zdarma a bez klíčů.
 * Rozhraní `VoiceInput` je malé schválně: v P3b ho nahradí lokální Whisper přes backend a rodič se nezmění.
 */

export type VoiceInputEvents = {
  /** Člověk začal mluvit (barge-in: rodič zastaví čtení odpovědi). */
  onSpeech: () => void;
  /** Průběžný přepis do pole. */
  onInterim: (text: string) => void;
  /** Dokončená myšlenka; samotný finál prohlížeče ji neodesílá. */
  onFinal: (text: string) => void;
  /** Kód chyby prohlížeče (`not-allowed`, `no-speech`, `network`, …); text dá `voiceError`. */
  onError: (code: string) => void;
  /** Logický poslech skončil; interní restart ani stop callback nevyvolají. */
  onEnd: () => void;
};
/** continuous allows multiple thoughts; endpointMs defaults to 8000, zero requires finish(). */
export type VoiceInput = { supported: boolean; start: (events: VoiceInputEvents, options?: { continuous?: boolean; endpointMs?: number }) => void; stop: () => void; finish: () => void; setEndpointMs: (value: number) => void };

type Alternative = { transcript: string };
type Result = { isFinal: boolean; 0: Alternative };
type Recognition = {
  lang: string; interimResults: boolean; continuous: boolean; maxAlternatives: number;
  onspeechstart: (() => void) | null;
  onspeechend: (() => void) | null;
  onresult: ((event: { results: ArrayLike<Result> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void; abort: () => void;
};
export type RecognitionCtor = new () => Recognition;

/** Chrome a Edge mají `webkitSpeechRecognition`; Firefox nic, pak je hlas skrytý. */
export function recognitionCtor(scope: object = globalThis): RecognitionCtor | null {
  const value = scope as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return value.SpeechRecognition ?? value.webkitSpeechRecognition ?? null;
}

/** OP-5AED6F: browser segments are not human turns; drafts survive recognition rollovers. */
export function createVoiceInput(Ctor: RecognitionCtor | null = recognitionCtor()): VoiceInput {
  let current: Recognition | null = null;
  let generation = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let restart: ReturnType<typeof setTimeout> | undefined;
  let finish = () => {};
  let setEndpointMs = (_value: number) => {};
  const stop = () => {
    generation++;
    clearTimeout(timer); clearTimeout(restart);
    finish = () => {}; setEndpointMs = () => {};
    const rec = current; current = null;
    try { rec?.abort(); } catch { /* already ended */ }
  };
  const start: VoiceInput["start"] = (events, { continuous = false, endpointMs = 8000 } = {}) => {
    stop();
    if (!Ctor) { events.onError("not-supported"); events.onEnd(); return; }
    const run = generation;
    let carried = "", segment = "";
    let consumed = 0, resultCount = 0;
    let deadlineArmed = false;
    let speaking = false, quietRestarts = 0;
    const alive = () => generation === run;
    const draft = () => [carried, segment].filter(Boolean).join(" ").trim();
    const fail = (code: string) => {
      if (!alive()) return;
      stop(); events.onError(code); events.onEnd();
    };
    finish = () => {
      if (!alive()) return;
      const text = draft();
      if (!text) return;
      clearTimeout(timer);
      deadlineArmed = false;
      carried = ""; segment = ""; consumed = resultCount;
      if (!continuous) stop();
      events.onFinal(text);
      if (!continuous) events.onEnd();
    };
    const arm = () => {
      clearTimeout(timer);
      deadlineArmed = !speaking && endpointMs > 0 && !!draft();
      if (deadlineArmed) timer = setTimeout(() => { if (alive()) finish(); }, endpointMs);
    };
    setEndpointMs = value => { endpointMs = Math.max(0, value); if (alive()) arm(); };
    const listen = () => {
      if (!alive()) return;
      const rec = new Ctor(); current = rec;
      consumed = 0; resultCount = 0; segment = "";
      rec.lang = "cs-CZ"; rec.interimResults = true; rec.continuous = true; rec.maxAlternatives = 1;
      const active = () => alive() && current === rec;
      rec.onspeechstart = () => {
        if (!active()) return;
        speaking = true; quietRestarts = 0;
        clearTimeout(timer); deadlineArmed = false; events.onSpeech();
      };
      rec.onspeechend = () => { if (active()) { speaking = false; arm(); } };
      rec.onresult = event => {
        if (!active()) return;
        const results = Array.from(event.results); resultCount = results.length;
        quietRestarts = 0;
        segment = results.slice(consumed).map(r => r[0].transcript.trim()).filter(Boolean).join(" ");
        events.onInterim(draft());
        if (active()) arm();
      };
      // Browser no-speech is an idle rollover, not a failed human thought.
      rec.onerror = event => { if (active() && event.error !== "no-speech") fail(event.error); };
      rec.onend = () => {
        if (!active()) return;
        carried = draft(); segment = ""; current = null; speaking = false;
        // Preserve an already running silence deadline across browser sessions.
        if (!deadlineArmed) arm();
        restart = setTimeout(listen, Math.min(4000, 100 * 2 ** Math.min(quietRestarts++, 6)));
      };
      try { rec.start(); } catch { fail("start"); }
    };
    listen();
  };
  return { supported: !!Ctor, start, stop, finish: () => finish(), setEndpointMs: value => setEndpointMs(value) };
}

/** Kód chyby → česká hláška; `null` = nic neříkat (ticho, vlastní stop). `blocked` zakáže tlačítko. */
export function voiceError(code: string): { text: string; blocked: boolean } | null {
  if (code === "no-speech" || code === "aborted") return null;
  if (code === "not-allowed" || code === "service-not-allowed") {
    return { text: "Mikrofon není povolený. Povol ho u adresy (ikona zámku) a obnov stránku.", blocked: true };
  }
  if (code === "network") return { text: "Rozpoznávání řeči nemá spojení se službou prohlížeče. Zkus to znovu, nebo napiš.", blocked: false };
  if (code === "audio-capture") return { text: "Mikrofon nenalezen. Zkontroluj, že je připojený.", blocked: false };
  if (code === "not-supported") return { text: "Tento prohlížeč hlas neumí; použij Chrome nebo Edge.", blocked: true };
  return { text: "Hlas se nepodařilo zachytit. Zkus to znovu, nebo napiš.", blocked: false };
}

/** Hlasitost mikrofonu 0–1 pro jádro HUD; `close` ukončí stream i zvukový kontext. */
export type MicLevel = { level: () => number; close: () => void };

/** Volitelné: když mikrofon nebo Web Audio selže, vrátí `null` a jádro jede na syntetické amplitudě. */
export async function openMicLevel(): Promise<MicLevel | null> {
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  } catch {
    return null;
  }
  const end = () => stream.getTracks().forEach((track) => track.stop());
  try {
    const audio = new AudioContext();
    const analyser = audio.createAnalyser();
    analyser.fftSize = 256;
    audio.createMediaStreamSource(stream).connect(analyser);
    const data = new Uint8Array(analyser.fftSize);
    return {
      level: () => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (const value of data) sum += ((value - 128) / 128) ** 2;
        return Math.min(1, Math.sqrt(sum / data.length) * 4);
      },
      close: () => { end(); void audio.close().catch(() => undefined); },
    };
  } catch {
    end();
    return null;
  }
}
