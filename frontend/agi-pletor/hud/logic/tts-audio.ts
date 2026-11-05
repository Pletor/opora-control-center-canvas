/** Zvuk hlasu serveru (`POST /api/pletor/tts`) pro `tts-output.ts`: stažení věty a převod na AudioBuffery. */

/** Zvuk jedné věty: celý soubor k dekódování, nebo proud PCM 16 bit LE mono v dané frekvenci. */
export type Sound = ArrayBuffer | { rate: number; chunks: AsyncIterable<Uint8Array> };
export type Speech = (text: string, voice: string, signal: AbortSignal) => Promise<Sound>;

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
export async function* audioBuffers(ctx: AudioContext, sound: Sound) {
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

export const browserAudio = () => {
  try {
    return typeof AudioContext === "function" ? new AudioContext() : null;
  } catch {
    return null;
  }
};
