import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GAVE_UP, MAX_RESTARTS, RESTART_MS, RESUME_MS, createListenLoop, restartPlan } from "./use-pletor-listen";
import type { VoiceInput, VoiceInputEvents } from "./voice-input";

/** Falešný vstup: pamatuje si události posledního startu, test pak sám hlásí věty, chyby a konec. */
function fakeInput() {
  const runs: VoiceInputEvents[] = [];
  const input: VoiceInput & { runs: VoiceInputEvents[]; last: () => VoiceInputEvents } = {
    supported: true, runs,
    start: vi.fn((events: VoiceInputEvents, options?: { continuous?: boolean }) => { expect(options?.continuous).toBe(true); runs.push(events); }),
    stop: vi.fn(),
    finish: vi.fn(), setEndpointMs: vi.fn(),
    last: () => runs[runs.length - 1],
  };
  return input;
}
const handlers = () => ({ onListening: vi.fn(), onInterim: vi.fn(), onCommand: vi.fn(), onFail: vi.fn() });

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(0); });
afterEach(() => vi.useRealTimers());

describe("restartPlan", () => {
  it("ticho obnoví hned a vynuluje pokusy, selhání s rostoucí prodlevou, po limitu vzdá", () => {
    expect(restartPlan(3, false)).toEqual({ attempt: 0, delay: RESTART_MS });
    expect(restartPlan(0, true)).toEqual({ attempt: 1, delay: 500 });
    expect(restartPlan(1, true)).toEqual({ attempt: 2, delay: 1000 });
    expect(restartPlan(5, true)).toEqual({ attempt: 6, delay: 8000 });
    expect(restartPlan(MAX_RESTARTS, true)).toBeNull();
  });
});

describe("createListenLoop", () => {
  it("pending thought blocks external pause, explicit finish forwards once and stop discards", () => {
    const input = fakeInput(); const on = handlers();
    let endpoint = 0;
    const loop = createListenLoop(input, on, () => false, () => endpoint);
    loop.start();
    expect(input.start).toHaveBeenLastCalledWith(expect.any(Object), { continuous: true, endpointMs: 0 });
    input.last().onSpeech();
    loop.pause();
    expect(input.stop).not.toHaveBeenCalled();
    input.last().onInterim("První věta a rozmyšlené pokračování");
    expect(loop.pending()).toBe(true);
    loop.finish(); expect(input.finish).toHaveBeenCalledTimes(1);
    input.last().onFinal("První věta a rozmyšlené pokračování");
    expect(on.onCommand).toHaveBeenCalledTimes(1);
    expect(loop.pending()).toBe(false);
    loop.finish(); expect(input.finish).toHaveBeenCalledTimes(1); // paused after submission
    endpoint = 12000; loop.resume(); vi.advanceTimersByTime(RESUME_MS);
    expect(input.start).toHaveBeenLastCalledWith(expect.any(Object), { continuous: true, endpointMs: 12000 });
    const old = input.last(); loop.stop(); old.onFinal("Pozdní výsledek nesmí odejít");
    expect(on.onCommand).toHaveBeenCalledTimes(1);
  });

  it("callbacks from a cancelled run cannot submit into a restarted loop", () => {
    const input = fakeInput(); const on = handlers();
    const loop = createListenLoop(input, on, () => false);
    loop.start(); const cancelled = input.last(); loop.stop(); loop.start();
    cancelled.onSpeech(); cancelled.onInterim("stará myšlenka"); cancelled.onFinal("stará myšlenka"); cancelled.onEnd();
    expect(on.onCommand).not.toHaveBeenCalled(); expect(loop.pending()).toBe(false);
    input.last().onFinal("nová myšlenka"); expect(on.onCommand).toHaveBeenCalledWith("nová myšlenka");
  });
  it("věta projde sítem, smyčka se pozastaví a po resume poslouchá znovu až po prodlevě", () => {
    const input = fakeInput();
    const on = handlers();
    const loop = createListenLoop(input, on, () => false);
    loop.start();
    expect(on.onListening).toHaveBeenLastCalledWith(true);
    input.last().onFinal("Co dělá srdce");
    expect(on.onCommand).toHaveBeenCalledWith("Co dělá srdce");
    expect(input.stop).toHaveBeenCalled();
    expect(on.onListening).toHaveBeenLastCalledWith(false);
    // Pauza během přemýšlení a čtení: žádný nový start, ani když čas běží.
    vi.advanceTimersByTime(10_000);
    expect(input.start).toHaveBeenCalledTimes(1);
    loop.resume();
    vi.advanceTimersByTime(RESUME_MS - 1);
    expect(input.start).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(1);
    expect(input.start).toHaveBeenCalledTimes(2);
  });

  it("pause během čtení utne poslech a stop/resume ho neobnoví, když je vypnuto", () => {
    const input = fakeInput();
    const loop = createListenLoop(input, handlers(), () => false);
    loop.start();
    loop.pause();
    expect(input.stop).toHaveBeenCalledTimes(1);
    loop.stop();
    loop.resume();
    vi.advanceTimersByTime(RESUME_MS * 2);
    expect(input.start).toHaveBeenCalledTimes(1);
    expect(loop.active()).toBe(false);
  });

  it("krátkou větu a duplicitu do 2 s zahodí a poslouchá dál; oslovení se odstraní", () => {
    const input = fakeInput();
    const on = handlers();
    let wake = false;
    createListenLoop(input, on, () => wake).start();
    input.last().onFinal("a");
    expect(on.onCommand).not.toHaveBeenCalled();
    wake = true;
    input.last().onFinal("nic pro tebe");
    expect(on.onCommand).not.toHaveBeenCalled();
    input.last().onFinal("Pletore, ukaž plán");
    expect(on.onCommand).toHaveBeenLastCalledWith("ukaž plán");
  });

  it("duplicita do 2 s se zahodí, po 2 s projde", () => {
    const input = fakeInput();
    const on = handlers();
    const loop = createListenLoop(input, on, () => false);
    loop.start();
    input.last().onFinal("ukaž plán");
    loop.resume();
    vi.advanceTimersByTime(RESUME_MS);
    input.last().onFinal("Ukaž plán");
    expect(on.onCommand).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(2000);
    input.last().onFinal("ukaž plán");
    expect(on.onCommand).toHaveBeenCalledTimes(2);
  });

  it("konec po tichu obnoví poslech, síťová chyba s backoffem a po limitu se vzdá", () => {
    const input = fakeInput();
    const on = handlers();
    createListenLoop(input, on, () => false).start();
    vi.advanceTimersByTime(5000);
    input.last().onError("no-speech");
    input.last().onEnd();
    vi.advanceTimersByTime(RESTART_MS);
    expect(input.start).toHaveBeenCalledTimes(2);
    for (let i = 0; i <= MAX_RESTARTS; i++) {
      input.last().onError("network");
      input.last().onEnd();
      vi.advanceTimersByTime(8000);
    }
    expect(input.start).toHaveBeenCalledTimes(2 + MAX_RESTARTS);
    expect(on.onFail).toHaveBeenCalledWith(GAVE_UP);
  });

  it("nepovolený mikrofon smyčku vypne a vrátí českou hlášku", () => {
    const input = fakeInput();
    const on = handlers();
    const loop = createListenLoop(input, on, () => false);
    loop.start();
    input.last().onError("not-allowed");
    input.last().onEnd();
    expect(on.onFail).toHaveBeenCalledWith(expect.stringContaining("Mikrofon není povolený"));
    expect(loop.active()).toBe(false);
    vi.advanceTimersByTime(10_000);
    expect(input.start).toHaveBeenCalledTimes(1);
  });
});
