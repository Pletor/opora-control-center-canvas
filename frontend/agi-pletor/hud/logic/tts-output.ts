/**
 * Hlas Pletora přes backend (`POST /api/pletor/tts`): XTTS, Edge nebo Piper podle zvoleného hlasu, se stejným
 * rozhraním `VoiceOutput` jako prohlížečová syntéza, která je poslední zálohou.
 * Rychlost: věty se syntetizují souběžně (nejvýš 2 v letu), první hraje hned a další navazují bez pauzy
 * v AudioContextu. MP3 (Edge) a WAV (Piper) se dekódují celé, PCM z XTTS hraje po kouscích, jak ho GPU vyrábí.
 * Plynulost: selže-li engine u první věty, přečte ji další hlas z řetězce (`voiceChain`). Jedna odpověď = jeden hlas:
 * další věty čtou jen hlasem první věty (selhání zkusí ještě jednou), až pak zbytek dočte prohlížeč.
 */
import { audioBuffers, browserAudio, fetchSpeech, type Sound, type Speech } from "./tts-audio";
import { splitSentences, type VoiceOutput, type VoiceOutputEvents } from "./voice-output";

/** Rozpracované čtení: `push` přidá text, `end` dočte zbytek a po dohrání zavolá `onEnd`; `stop` výstupu ho utne. */
export type VoiceStream = { push: (text: string) => void; end: () => void };
export type ServerOutput = VoiceOutput & { level: () => number | null; begin: (events: VoiceOutputEvents) => VoiceStream };

const IN_FLIGHT = 2;

/** `chain()` je řetězec hlasů ke čtení (`voiceChain`), prázdný = rovnou prohlížeč. */
export function createServerOutput(fallback: VoiceOutput, chain: () => string[], speech: Speech = fetchSpeech,
  makeAudio: () => AudioContext | null = browserAudio): ServerOutput {
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

  /** Čtení po kouscích textu (proud odpovědi): dokončená věta se hned objedná a řadí, poslední čeká na další `push` nebo `end`. */
  const begin = (events: VoiceOutputEvents): VoiceStream => {
    stop();
    const mine = token;
    const voices = chain();
    const sound = voices.length ? context() : null;
    const sentences: string[] = [];
    let text = "";
    let ended = false;
    let wake = () => undefined as void; // probudí přehrávač, když přibude věta nebo konec
    let server = !!sound;
    // Prohlížeč (bez hlasu serveru, nebo když žádný nečte) čte nasbírané věty po dávkách; konec až po `end` a poslední dávce.
    let browser = !sound;
    let spoken = 0;
    let busy = false;
    let finished = false;
    const finish = () => { if (mine === token && !finished) { finished = true; playing = []; events.onEnd(); } };
    const speakBrowser = () => {
      if (!browser || busy || mine !== token) return;
      if (spoken < sentences.length) {
        const batch = sentences.slice(spoken).join(" ");
        spoken = sentences.length;
        busy = true;
        fallback.speak(batch, { onBoundary: events.onBoundary, onEnd: () => { busy = false; speakBrowser(); } });
      } else if (ended) finish();
    };
    const controller = new AbortController();
    abort = controller;
    type Loaded = { id: string; sound: Sound };
    // OP-FB0522.m1d: hlas se uprostřed odpovědi nestřídá; řetězec záloh platí jen pro první větu
    const load = async (sentence: string, first?: Promise<Loaded>): Promise<Loaded> => {
      if (!first) {
        for (const id of voices) {
          try {
            return { id, sound: await speech(sentence, id, controller.signal) };
          } catch (error) {
            if (controller.signal.aborted) throw error;
          }
        }
        throw new Error("Žádný hlas serveru nečte");
      }
      // Souběžně s první větou zkusí hlavní hlas; hraje jen, když první větu přečetl týž hlas. Jinak (i po chybě)
      // větu přečte ještě jednou hlas první věty.
      const early = speech(sentence, voices[0], controller.signal).catch(() => null);
      const { id } = await first;
      const sound = id === voices[0] ? await early : null;
      return { id, sound: sound ?? await speech(sentence, id, controller.signal) };
    };
    const queue: Promise<Loaded>[] = [];
    let taken = 0; // věty, které přehrávač už převzal
    const fill = () => {
      while (server && queue.length < sentences.length && queue.length < taken + IN_FLIGHT) {
        const loaded = load(sentences[queue.length], queue[0]);
        loaded.catch(() => undefined); // zrušené dopředu stažené věty nejsou chyba
        queue.push(loaded);
      }
    };
    const add = () => {
      const parts = text.split(/(?<=[.!?…])\s+/);
      text = ended ? "" : parts.pop()!;
      sentences.push(...splitSentences(parts.join(" ")));
      fill();
      wake();
      speakBrowser();
    };
    const handle: VoiceStream = {
      push: (more) => { if (mine === token && !ended) { text += more; add(); } },
      end: () => { if (mine === token && !ended) { ended = true; add(); } },
    };
    if (!sound) return handle;
    const { context: ctx, analyser } = sound;
    void ctx.resume().catch(() => undefined);
    const started = performance.now();
    void (async () => {
      let end = 0;
      let heard = false;
      for (let i = 0; ; i++) {
        while (i >= sentences.length && !ended) {
          await new Promise<void>((resolve) => { wake = resolve; });
          if (mine !== token) return;
        }
        if (i >= sentences.length) break;
        let loaded: Loaded;
        try {
          loaded = await queue[i];
          if (ctx.state === "suspended") throw new Error("AudioContext nesmí hrát");
        } catch {
          if (mine !== token) return;
          // Žádný engine nečte (nebo AudioContext nesmí hrát): zbytek dočte prohlížeč, až dohraje, co už zní.
          server = false;
          setTimeout(() => { browser = true; spoken = i; speakBrowser(); }, Math.max(0, end - ctx.currentTime) * 1000);
          return;
        }
        if (mine !== token) return;
        taken = i + 1;
        fill();
        try {
          for await (const buffer of audioBuffers(ctx, loaded.sound)) {
            if (mine !== token) return;
            const source = ctx.createBufferSource();
            source.buffer = buffer;
            source.connect(analyser);
            const when = Math.max(ctx.currentTime, end);
            source.start(when);
            end = when + buffer.duration;
            playing.push(source);
            if (!heard) console.debug(`Pletor TTFA ${Math.round(performance.now() - started)} ms (${loaded.id})`);
            heard = true;
          }
        } catch {
          if (mine !== token) return; // useknutý proud nebo vadný zvuk: věta končí tím, co zaznělo, čte se dál
        }
      }
      if (mine !== token) return;
      const last = playing.at(-1);
      if (last && end > ctx.currentTime) last.onended = finish;
      else finish();
    })();
    return handle;
  };

  /** Celá odpověď najednou = proud z jednoho kusu. */
  const speak = (text: string, events: VoiceOutputEvents) => {
    const reading = begin(events);
    reading.push(text);
    reading.end();
  };

  /** Hlasitost právě hraného zvuku (RMS) pro jádro HUD; mimo hlas serveru `null` a hook vezme syntetický puls. */
  const level = () => {
    if (!audio || !playing.length) return null;
    audio.analyser.getByteTimeDomainData(audio.data);
    let sum = 0;
    for (const value of audio.data) sum += ((value - 128) / 128) ** 2;
    return Math.min(1, Math.sqrt(sum / audio.data.length) * 4);
  };

  return { supported: fallback.supported || typeof AudioContext === "function", speak, begin, stop, level };
}
