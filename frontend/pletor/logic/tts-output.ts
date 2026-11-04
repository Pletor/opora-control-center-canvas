/**
 * Hlas Pletora přes backend (`POST /api/pletor/tts`): XTTS, Edge nebo Piper podle zvoleného hlasu, se stejným
 * rozhraním `VoiceOutput` jako prohlížečová syntéza, která je poslední zálohou.
 * Rychlost: věty se syntetizují souběžně (nejvýš 2 v letu), první hraje hned a další navazují bez pauzy
 * v AudioContextu. MP3 (Edge) a WAV (Piper) se dekódují celé, PCM z XTTS hraje po kouscích, jak ho GPU vyrábí.
 * Plynulost: selže-li engine, tutéž větu přečte další hlas z řetězce (`voiceChain`), až nakonec prohlížeč.
 */
import { splitSentences, type VoiceOutput, type VoiceOutputEvents } from "./voice-output";

/** Zvuk jedné věty: celý soubor k dekódování, nebo proud PCM 16 bit LE mono v dané frekvenci. */
export type Sound = ArrayBuffer | { rate: number; chunks: AsyncIterable<Uint8Array> };
type Speech = (text: string, voice: string, signal: AbortSignal) => Promise<Sound>;
export type ServerOutput = VoiceOutput & { level: () => number | null };

const IN_FLIGHT = 2;

async function* bodyChunks(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    yield value;
  }
}

// shortcut: cookie člověka už existuje (odpověď přišla přes api POST); po restartu serveru 428 → čte prohlížeč, dokud nepřijde další zpráva.
export const fetchSpeech: Speech = async (text, voice, signal) => {
  const response = await fetch("/api/pletor/tts", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, voice }), signal,
  });
  if (!response.ok) throw new Error(`Hlas Pletora: HTTP ${response.status}`);
  const rate = /^audio\/pcm;\s*rate=(\d+)/.exec(response.headers.get("Content-Type") ?? "")?.[1];
  return rate && response.body ? { rate: Number(rate), chunks: bodyChunks(response.body) } : response.arrayBuffer();
};

/** PCM 16 bit little-endian → vzorky -1…1 pro AudioBuffer. */
export function pcmSamples(bytes: Uint8Array): Float32Array<ArrayBuffer> {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const samples = new Float32Array(bytes.byteLength >> 1);
  for (let i = 0; i < samples.length; i++) samples[i] = view.getInt16(i * 2, true) / 32768;
  return samples;
}

/** AudioBuffery jedné věty: soubor celý, PCM po kouscích (lichý bajt na hranici kousku počká na další). */
async function* audioBuffers(ctx: AudioContext, sound: Sound) {
  if (sound instanceof ArrayBuffer) { yield await ctx.decodeAudioData(sound); return; }
  let rest = new Uint8Array(0);
  for await (const chunk of sound.chunks) {
    const bytes = rest.length ? new Uint8Array([...rest, ...chunk]) : chunk;
    const even = bytes.length - (bytes.length % 2);
    rest = bytes.slice(even);
    if (!even) continue;
    const samples = pcmSamples(bytes.subarray(0, even));
    const buffer = ctx.createBuffer(1, samples.length, sound.rate);
    buffer.copyToChannel(samples, 0);
    yield buffer;
  }
}

const browserAudio = () => {
  try {
    return typeof AudioContext === "function" ? new AudioContext() : null;
  } catch {
    return null;
  }
};

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

  const speak = (text: string, events: VoiceOutputEvents) => {
    stop();
    const voices = chain();
    const sound = voices.length ? context() : null;
    if (!sound) { fallback.speak(text, events); return; }
    const sentences = splitSentences(text);
    if (!sentences.length) { events.onEnd(); return; }
    const { context: ctx, analyser } = sound;
    const mine = token;
    const controller = new AbortController();
    abort = controller;
    void ctx.resume().catch(() => undefined);
    const started = performance.now();
    const failed = new Set<string>(); // engine, který v této odpovědi selhal, se u dalších vět přeskočí
    const load = async (sentence: string) => {
      for (const id of voices) {
        if (failed.has(id)) continue;
        try {
          return { id, sound: await speech(sentence, id, controller.signal) };
        } catch (error) {
          if (controller.signal.aborted) throw error;
          failed.add(id);
        }
      }
      throw new Error("Žádný hlas serveru nečte");
    };
    const fetchSentence = (sentence: string) => {
      const loaded = load(sentence);
      loaded.catch(() => undefined); // zrušené dopředu stažené věty nejsou chyba
      return loaded;
    };
    const queue = sentences.slice(0, IN_FLIGHT).map(fetchSentence);
    void (async () => {
      let end = 0;
      let heard = false;
      for (let i = 0; i < sentences.length; i++) {
        let loaded: Awaited<ReturnType<typeof load>>;
        try {
          loaded = await queue[i];
          if (ctx.state === "suspended") throw new Error("AudioContext nesmí hrát");
        } catch {
          if (mine !== token) return;
          // Žádný engine nečte (nebo AudioContext nesmí hrát): zbytek dočte prohlížeč, až dohraje, co už zní.
          const rest = sentences.slice(i).join(" ");
          setTimeout(() => { if (mine === token) fallback.speak(rest, events); }, Math.max(0, end - ctx.currentTime) * 1000);
          return;
        }
        if (mine !== token) return;
        if (queue.length < sentences.length) queue.push(fetchSentence(sentences[queue.length]));
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
      const done = () => { if (mine === token) { playing = []; events.onEnd(); } };
      const last = playing.at(-1);
      if (last && end > ctx.currentTime) last.onended = done;
      else done();
    })();
  };

  /** Hlasitost právě hraného zvuku (RMS) pro jádro HUD; mimo hlas serveru `null` a hook vezme syntetický puls. */
  const level = () => {
    if (!audio || !playing.length) return null;
    audio.analyser.getByteTimeDomainData(audio.data);
    let sum = 0;
    for (const value of audio.data) sum += ((value - 128) / 128) ** 2;
    return Math.min(1, Math.sqrt(sum / audio.data.length) * 4);
  };

  return { supported: fallback.supported || typeof AudioContext === "function", speak, stop, level };
}
