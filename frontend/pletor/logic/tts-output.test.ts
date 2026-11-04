import { describe, expect, it, vi } from "vitest";
import { createServerOutput, pcmSamples, type Sound } from "./tts-output";
import type { VoiceOutput } from "./voice-output";

const JIRKA = "cs_CZ-jirka-medium";
const XTTS = "xtts:default";
const EDGE = "edge:cs-CZ-AntoninNeural";

/** Falešný server: každý požadavek čeká, test ho vyřídí (`answer`) nebo odmítne (`fail`). */
function fakeSpeech() {
  type Call = { text: string; voice: string; signal: AbortSignal; resolve: (sound: Sound) => void; reject: (error: Error) => void };
  const calls: Call[] = [];
  const speech = vi.fn((text: string, voice: string, signal: AbortSignal) =>
    new Promise<Sound>((resolve, reject) => calls.push({ text, voice, signal, resolve, reject })));
  const inFlight = () => calls.filter((call) => !("done" in call)).length;
  const answer = (index: number, seconds: number) => {
    Object.assign(calls[index], { done: true });
    calls[index].resolve(new ArrayBuffer(seconds * 10));
  };
  const fail = (index: number) => { Object.assign(calls[index], { done: true }); calls[index].reject(new Error("HTTP 503")); };
  return { calls, speech, inFlight, answer, fail };
}

/** Falešný AudioContext: soubor trvá `bytes / 10` s, PCM buffer `vzorky / frekvence`; `onended` pouští test. */
function fakeAudio() {
  type Node = { startAt: number | null; stopped: boolean; onended: (() => void) | null; buffer: { duration: number } | null };
  const sources: Node[] = [];
  const context = {
    currentTime: 0, state: "running", destination: {},
    resume: vi.fn(() => Promise.resolve()),
    decodeAudioData: (data: ArrayBuffer) => Promise.resolve({ duration: data.byteLength / 10 }),
    createBuffer: (_: number, length: number, rate: number) => ({ duration: length / rate, copyToChannel: vi.fn() }),
    createAnalyser: () => ({ fftSize: 0, connect: vi.fn(), getByteTimeDomainData: (data: Uint8Array) => data.fill(200) }),
    createBufferSource: () => {
      const node = { startAt: null as number | null, stopped: false, onended: null as (() => void) | null, buffer: null,
        connect: vi.fn(), start(when: number) { node.startAt = when; }, stop() { node.stopped = true; } };
      sources.push(node);
      return node;
    },
  };
  return { context: context as unknown as AudioContext, sources };
}

function fakeFallback(): VoiceOutput & { speak: ReturnType<typeof vi.fn>; stop: ReturnType<typeof vi.fn> } {
  return { supported: true, speak: vi.fn((_: string, events: { onEnd: () => void }) => events.onEnd()), stop: vi.fn() };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("pcmSamples", () => {
  it("16 bit little-endian → -1…1", () => {
    expect(Array.from(pcmSamples(new Uint8Array([0x00, 0x40, 0x00, 0xc0, 0xff, 0x7f])))).toEqual([0.5, -0.5, 32767 / 32768]);
  });
});

describe("createServerOutput", () => {
  it("první věta hned, nejvýš 2 v letu, věty navazují bez pauzy a konec po poslední", async () => {
    const server = fakeSpeech();
    const { context, sources } = fakeAudio();
    const fallback = fakeFallback();
    const onEnd = vi.fn();
    const output = createServerOutput(fallback, () => [JIRKA], server.speech, () => context);
    output.speak("Jedna. Dvě. Tři. Čtyři.", { onEnd });
    await flush();
    expect(server.calls.map((call) => call.text)).toEqual(["Jedna.", "Dvě."]);
    expect(server.calls[0].voice).toBe(JIRKA);
    server.answer(1, 2); // druhá věta dřív než první: hraje se stejně v pořadí
    await flush();
    expect(sources).toHaveLength(0);
    server.answer(0, 1);
    await flush();
    expect(server.inFlight()).toBeLessThanOrEqual(2);
    expect(server.calls.map((call) => call.text)).toEqual(["Jedna.", "Dvě.", "Tři.", "Čtyři."]);
    server.answer(2, 1);
    server.answer(3, 3);
    await flush();
    expect(sources.map((source) => source.startAt)).toEqual([0, 1, 3, 4]);
    expect(output.level()).toBeGreaterThan(0);
    expect(onEnd).not.toHaveBeenCalled();
    sources[3].onended?.();
    expect(onEnd).toHaveBeenCalledOnce();
    expect(output.level()).toBeNull();
    expect(fallback.speak).not.toHaveBeenCalled();
  });

  it("PCM z XTTS hraje po kouscích hned, jak přijdou, i s lichým bajtem na hranici", async () => {
    const { context, sources } = fakeAudio();
    let push: (chunk: Uint8Array | null) => void = () => undefined;
    const chunks = (async function* () {
      for (;;) {
        const chunk = await new Promise<Uint8Array | null>((resolve) => { push = resolve; });
        if (!chunk) return;
        yield chunk;
      }
    })();
    const speech = vi.fn(() => Promise.resolve<Sound>({ rate: 4, chunks }));
    const onEnd = vi.fn();
    createServerOutput(fakeFallback(), () => [XTTS], speech, () => context).speak("Jedna.", { onEnd });
    await flush();
    push(new Uint8Array(9)); // 4 vzorky = 1 s, lichý bajt počká
    await flush();
    expect(sources.map((source) => source.startAt)).toEqual([0]);
    push(new Uint8Array(7)); // + 1 bajt = 4 vzorky
    await flush();
    push(null);
    await flush();
    expect(sources.map((source) => [source.startAt, source.buffer?.duration])).toEqual([[0, 1], [1, 1]]);
    sources[1].onended?.();
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it("selže-li engine, tutéž větu přečte další hlas z řetězce a selhaný engine se už nezkouší", async () => {
    const server = fakeSpeech();
    const { context, sources } = fakeAudio();
    const fallback = fakeFallback();
    createServerOutput(fallback, () => [XTTS, EDGE, JIRKA], server.speech, () => context).speak("Jedna. Dvě. Tři.", { onEnd: vi.fn() });
    await flush();
    expect(server.calls.map((call) => call.voice)).toEqual([XTTS, XTTS]);
    server.fail(0);
    await flush();
    expect(server.calls.map((call) => [call.text, call.voice])).toContainEqual(["Jedna.", EDGE]);
    server.answer(2, 1);
    server.fail(1);
    await flush();
    expect(sources).toHaveLength(1);
    const later = server.calls.slice(3).map((call) => [call.text, call.voice]);
    expect(later).toEqual(expect.arrayContaining([["Dvě.", EDGE], ["Tři.", EDGE]]));
    expect(fallback.speak).not.toHaveBeenCalled();
  });

  it("barge-in: stop zastaví zvuk, zruší rozjeté požadavky a nic dalšího nepřehraje", async () => {
    const server = fakeSpeech();
    const { context, sources } = fakeAudio();
    const onEnd = vi.fn();
    const output = createServerOutput(fakeFallback(), () => [EDGE, JIRKA], server.speech, () => context);
    output.speak("Jedna. Dvě. Tři.", { onEnd });
    await flush();
    server.answer(0, 1);
    await flush();
    expect(sources).toHaveLength(1);
    output.stop();
    expect(sources[0].stopped).toBe(true);
    expect(server.calls.every((call) => call.signal.aborted)).toBe(true);
    server.fail(1); // zrušený požadavek není chyba enginu: další hlas se nezkouší
    server.answer(2, 1);
    await flush();
    expect(server.calls.map((call) => call.voice)).not.toContain(JIRKA);
    expect(sources).toHaveLength(1);
    sources[0].onended?.();
    expect(onEnd).not.toHaveBeenCalled();
  });

  it("když nečte žádný hlas serveru, odpověď dočte prohlížeč", async () => {
    const server = fakeSpeech();
    const { context } = fakeAudio();
    const fallback = fakeFallback();
    const onEnd = vi.fn();
    createServerOutput(fallback, () => [JIRKA], server.speech, () => context).speak("Jedna. Dvě.", { onEnd });
    await flush();
    server.fail(0);
    await flush();
    await flush();
    expect(fallback.speak).toHaveBeenCalledWith("Jedna. Dvě.", expect.anything());
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it("volba Prohlížeč nebo bez Web Audio jde rovnou na prohlížeč", () => {
    const server = fakeSpeech();
    const fallback = fakeFallback();
    createServerOutput(fallback, () => [], server.speech, () => fakeAudio().context).speak("Ahoj.", { onEnd: vi.fn() });
    createServerOutput(fallback, () => [JIRKA], server.speech, () => null).speak("Ahoj.", { onEnd: vi.fn() });
    expect(fallback.speak).toHaveBeenCalledTimes(2);
    expect(server.speech).not.toHaveBeenCalled();
  });
});
