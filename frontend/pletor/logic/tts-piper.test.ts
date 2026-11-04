import { describe, expect, it, vi } from "vitest";
import { BROWSER_VOICE, chosenVoice, createPiperOutput, parseVoices } from "./tts-piper";
import type { VoiceOutput } from "./voice-output";

const JIRKA = { id: "cs_CZ-jirka-medium", label: "Jirka", gender: "male" as const };
const KASANDRA = { id: "cs_CZ-kasandra-medium", label: "Kasandra", gender: "female" as const };

/** Falešný server: každý požadavek čeká, test ho vyřídí (`answer`) nebo odmítne (`fail`). */
function fakeSpeech() {
  const calls: { text: string; voice: string; signal: AbortSignal; resolve: (data: ArrayBuffer) => void; reject: (error: Error) => void }[] = [];
  const speech = vi.fn((text: string, voice: string, signal: AbortSignal) =>
    new Promise<ArrayBuffer>((resolve, reject) => calls.push({ text, voice, signal, resolve, reject })));
  const inFlight = () => calls.filter((call) => !("done" in call)).length;
  const answer = (index: number, seconds: number) => {
    Object.assign(calls[index], { done: true });
    calls[index].resolve(new ArrayBuffer(seconds * 10));
  };
  const fail = (index: number) => { Object.assign(calls[index], { done: true }); calls[index].reject(new Error("HTTP 404")); };
  return { calls, speech, inFlight, answer, fail };
}

/** Falešný AudioContext: buffer trvá `bytes / 10` s, zdroj si pamatuje čas startu, `onended` pouští test. */
function fakeAudio() {
  type Node = { startAt: number | null; stopped: boolean; onended: (() => void) | null };
  const sources: Node[] = [];
  const context = {
    currentTime: 0, state: "running", destination: {},
    resume: vi.fn(() => Promise.resolve()),
    decodeAudioData: (data: ArrayBuffer) => Promise.resolve({ duration: data.byteLength / 10 }),
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

describe("parseVoices a chosenVoice", () => {
  it("bere jen platné hlasy a výchozí mezi nimi", () => {
    expect(parseVoices({ available: [JIRKA, { id: 1 }], default: "cs_CZ-jirka-medium" })).toEqual({ available: [JIRKA], default: JIRKA.id });
    expect(parseVoices({ available: [KASANDRA], default: "x" })).toEqual({ available: [KASANDRA], default: null });
    expect(parseVoices(null)).toEqual({ available: [], default: null });
  });
  it("volba Jirka / Kasandra / Prohlížeč, bez volby výchozí stažený", () => {
    const voices = { available: [JIRKA, KASANDRA], default: JIRKA.id };
    expect(chosenVoice(null, voices)).toBe(JIRKA.id);
    expect(chosenVoice(KASANDRA.id, voices)).toBe(KASANDRA.id);
    expect(chosenVoice(BROWSER_VOICE, voices)).toBeNull();
    expect(chosenVoice(KASANDRA.id, { available: [JIRKA], default: JIRKA.id })).toBe(JIRKA.id); // smazaný hlas
    expect(chosenVoice(null, { available: [], default: null })).toBeNull();
  });
});

describe("createPiperOutput", () => {
  it("první věta hned, nejvýš 2 v letu, věty navazují bez pauzy a konec po poslední", async () => {
    const server = fakeSpeech();
    const { context, sources } = fakeAudio();
    const fallback = fakeFallback();
    const onEnd = vi.fn();
    const output = createPiperOutput(fallback, () => JIRKA.id, server.speech, () => context);
    output.speak("Jedna. Dvě. Tři. Čtyři.", { onEnd });
    expect(server.calls.map((call) => call.text)).toEqual(["Jedna.", "Dvě."]);
    expect(server.calls[0].voice).toBe(JIRKA.id);
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

  it("barge-in: stop zastaví zvuk, zruší rozjeté požadavky a nic dalšího nepřehraje", async () => {
    const server = fakeSpeech();
    const { context, sources } = fakeAudio();
    const onEnd = vi.fn();
    const output = createPiperOutput(fakeFallback(), () => JIRKA.id, server.speech, () => context);
    output.speak("Jedna. Dvě. Tři.", { onEnd });
    server.answer(0, 1);
    await flush();
    expect(sources).toHaveLength(1);
    output.stop();
    expect(sources[0].stopped).toBe(true);
    expect(server.calls.every((call) => call.signal.aborted)).toBe(true);
    server.answer(1, 1);
    server.answer(2, 1);
    await flush();
    expect(sources).toHaveLength(1);
    sources[0].onended?.();
    expect(onEnd).not.toHaveBeenCalled();
  });

  it("chybějící hlas (404): odpověď dočte prohlížeč", async () => {
    const server = fakeSpeech();
    const { context } = fakeAudio();
    const fallback = fakeFallback();
    const onEnd = vi.fn();
    createPiperOutput(fallback, () => JIRKA.id, server.speech, () => context).speak("Jedna. Dvě.", { onEnd });
    server.fail(0);
    await flush();
    await flush();
    expect(fallback.speak).toHaveBeenCalledWith("Jedna. Dvě.", expect.anything());
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it("volba Prohlížeč nebo bez Web Audio jde rovnou na prohlížeč", () => {
    const server = fakeSpeech();
    const fallback = fakeFallback();
    createPiperOutput(fallback, () => null, server.speech, () => fakeAudio().context).speak("Ahoj.", { onEnd: vi.fn() });
    createPiperOutput(fallback, () => JIRKA.id, server.speech, () => null).speak("Ahoj.", { onEnd: vi.fn() });
    expect(fallback.speak).toHaveBeenCalledTimes(2);
    expect(server.speech).not.toHaveBeenCalled();
  });
});
