/**
 * Hlasový vstup Pletora (P3): prohlížečové rozpoznávání řeči (cs-CZ), zdarma a bez klíčů.
 * Rozhraní `VoiceInput` je malé schválně: v P3b ho nahradí lokální Whisper přes backend a rodič se nezmění.
 */

export type VoiceInputEvents = {
  /** Člověk začal mluvit (barge-in: rodič zastaví čtení odpovědi). */
  onSpeech: () => void;
  /** Průběžný přepis do pole. */
  onInterim: (text: string) => void;
  /** Hotová věta; přijde nejvýš jednou za start a rodič ji hned odešle. */
  onFinal: (text: string) => void;
  /** Kód chyby prohlížeče (`not-allowed`, `no-speech`, `network`, …); text dá `voiceError`. */
  onError: (code: string) => void;
  /** Poslech skončil (věta, ticho, chyba nebo stop). */
  onEnd: () => void;
};
/** `continuous` (přepínač Poslech): poslech neskončí první větou, každá hotová věta přijde zvlášť.
 *  `endpointMs` (výchozí 700, 0 = vypnuto): ustálený průběžný přepis se pošle jako věta dřív, než prohlížeč řekne „finální“. */
export type VoiceInput = { supported: boolean; start: (events: VoiceInputEvents, options?: { continuous?: boolean; endpointMs?: number }) => void; stop: () => void };

type Alternative = { transcript: string };
type Result = { isFinal: boolean; 0: Alternative };
type Recognition = {
  lang: string; interimResults: boolean; continuous: boolean; maxAlternatives: number;
  onspeechstart: (() => void) | null;
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

/** Výchozí je jedna věta na start (`continuous: false`): prohlížeč sám pozná ticho a pošle finální přepis.
 *  Trvalý poslech posílá každou novou hotovou větu; výsledky už poslané se přeskočí. */
export function createVoiceInput(Ctor: RecognitionCtor | null = recognitionCtor()): VoiceInput {
  let current: Recognition | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined; // endpointing: odpočet ticha nad průběžným přepisem
  const stop = () => {
    clearTimeout(timer);
    const rec = current;
    current = null;
    try { rec?.abort(); } catch { /* už neběží */ }
  };
  const start = (events: VoiceInputEvents, { continuous = false, endpointMs = 700 } = {}) => {
    stop();
    if (!Ctor) { events.onError("not-supported"); events.onEnd(); return; }
    const rec = new Ctor();
    current = rec;
    rec.lang = "cs-CZ";
    rec.interimResults = true;
    rec.continuous = continuous;
    rec.maxAlternatives = 1;
    let sent = false;
    let done = 0; // trvalý poslech: výsledky před tímto indexem už odešly jako věty
    rec.onspeechstart = () => { if (current === rec) events.onSpeech(); };
    rec.onresult = (event) => {
      if (current !== rec || sent) return;
      clearTimeout(timer);
      let final = "", interim = "";
      const results = Array.from(event.results);
      for (let i = done; i < results.length; i++) {
        if (results[i].isFinal) { final += results[i][0].transcript; if (continuous) done = i + 1; } else interim += results[i][0].transcript;
      }
      const text = interim.trim();
      if (final.trim()) { sent = !continuous; events.onFinal(final.trim()); return; }
      if (!text) return;
      events.onInterim(text);
      // Chrome posílá finální výsledek až 1–2 s po konci řeči; ustálený přepis stačí. Pozdní finál týchž výsledků se zahodí.
      if (endpointMs > 0 && (text.split(/\s+/).length >= 2 || text.length >= 8)) {
        timer = setTimeout(() => {
          if (current !== rec) return;
          if (continuous) done = results.length; else sent = true;
          events.onFinal(text);
        }, endpointMs);
      }
    };
    rec.onerror = (event) => { if (current === rec) events.onError(event.error); };
    rec.onend = () => { if (current === rec) { clearTimeout(timer); current = null; events.onEnd(); } };
    try {
      rec.start();
    } catch {
      current = null;
      events.onError("start");
      events.onEnd();
    }
  };
  return { supported: !!Ctor, start, stop };
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
