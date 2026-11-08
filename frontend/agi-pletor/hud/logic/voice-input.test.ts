import { afterEach, describe, expect, it, vi } from "vitest";
import { createVoiceInput, recognitionCtor, voiceError, type RecognitionCtor, type VoiceInputEvents } from "./voice-input";

/** Falešné SpeechRecognition: zapamatuje si poslední instanci, test pak sám posílá výsledky a konec. */
class FakeRecognition {
  static last: FakeRecognition;
  lang = ""; interimResults = false; continuous = true; maxAlternatives = 0;
  onspeechstart: (() => void) | null = null;
  onspeechend: (() => void) | null = null;
  onresult: ((event: { results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  start = vi.fn();
  abort = vi.fn(() => this.onend?.());
  constructor() { FakeRecognition.last = this; }
  say(parts: [string, boolean][]) { this.onresult?.({ results: parts.map(([transcript, isFinal]) => ({ isFinal, 0: { transcript } })) }); }
}
const Ctor = FakeRecognition as unknown as RecognitionCtor;

function events(): VoiceInputEvents & Record<string, ReturnType<typeof vi.fn>> {
  return { onSpeech: vi.fn(), onInterim: vi.fn(), onFinal: vi.fn(), onError: vi.fn(), onEnd: vi.fn() };
}

describe("thought aggregation", () => {
  afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });
  function begin(options = {}) {
    vi.useFakeTimers(); const on = events(); const input = createVoiceInput(Ctor);
    input.start(on, options); return { on, input, rec: FakeRecognition.last };
  }
  it("uses continuous Czech recognition even for a single manually started thought", () => {
    const {rec} = begin(); expect([rec.lang,rec.interimResults,rec.continuous]).toEqual(["cs-CZ",true,true]);
  });
  it("combines final segments and interim into one thought after eight seconds", () => {
    const {on,rec} = begin(); rec.say([["First sentence.",true]]);
    vi.advanceTimersByTime(7000); rec.say([["First sentence.",true],["Second",false]]);
    expect(on.onInterim).toHaveBeenLastCalledWith("First sentence. Second");
    rec.say([["First sentence.",true],["Second sentence.",true]]);
    vi.advanceTimersByTime(7999); expect(on.onFinal).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1); expect(on.onFinal).toHaveBeenCalledExactlyOnceWith("First sentence. Second sentence.");
    expect(on.onEnd).toHaveBeenCalledOnce();
  });
  it("speech start cancels silence; speech end rearms it", () => {
    const {on,rec} = begin(); rec.say([["A thought",true]]); vi.advanceTimersByTime(7000);
    rec.onspeechstart?.(); vi.advanceTimersByTime(9000); expect(on.onFinal).not.toHaveBeenCalled();
    rec.onspeechend?.(); vi.advanceTimersByTime(8000); expect(on.onFinal).toHaveBeenCalledOnce();
  });
  it("manual mode never submits browser finals; finish submits once", () => {
    const {input,on,rec} = begin({endpointMs:0}); rec.say([["First",true],["unfinished",false]]);
    vi.advanceTimersByTime(60000); expect(on.onFinal).not.toHaveBeenCalled();
    input.finish(); input.finish(); rec.say([["late",true]]);
    expect(on.onFinal).toHaveBeenCalledExactlyOnceWith("First unfinished");
  });
  it("stop discards, cancels restart and fences all late events", () => {
    const {input,on,rec} = begin(); rec.say([["Discard",true]]); rec.onend?.(); input.stop();
    rec.say([["late",true]]); rec.onerror?.({error:"network"}); rec.onend?.();
    vi.advanceTimersByTime(20000); input.finish();
    expect(on.onFinal).not.toHaveBeenCalled(); expect(on.onError).not.toHaveBeenCalled(); expect(on.onEnd).not.toHaveBeenCalled();
    expect(FakeRecognition.last).toBe(rec);
  });
  it("natural end preserves the draft and original deadline", () => {
    const {on,rec} = begin(); rec.say([["Retained",true]]); vi.advanceTimersByTime(5000); rec.onend?.();
    vi.advanceTimersByTime(100); expect(FakeRecognition.last).not.toBe(rec);
    expect(on.onEnd).not.toHaveBeenCalled(); vi.advanceTimersByTime(2899); expect(on.onFinal).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1); expect(on.onFinal).toHaveBeenCalledExactlyOnceWith("Retained");
  });
  it("combines transcripts across browser sessions and ignores old session events", () => {
    const {on,input,rec} = begin({endpointMs:0}); rec.say([["Before restart",true]]); rec.onend?.();
    vi.advanceTimersByTime(100); const next=FakeRecognition.last; next.say([["after restart",false]]);
    rec.say([["obsolete",true]]); expect(on.onInterim).toHaveBeenLastCalledWith("Before restart after restart");
    input.finish(); expect(on.onFinal).toHaveBeenCalledExactlyOnceWith("Before restart after restart");
  });
  it("continuous mode sends separate accumulated turns without replaying browser finals", () => {
    const {on,input,rec} = begin({continuous:true,endpointMs:0}); rec.say([["One",false]]); input.finish();
    rec.say([["One corrected",true]]); input.finish();
    rec.say([["One corrected",true],["Two",true],["Three",false]]); input.finish();
    expect(vi.mocked(on.onFinal).mock.calls).toEqual([["One"],["Two Three"]]); expect(on.onEnd).not.toHaveBeenCalled();
  });
  it("changing to manual cancels pending submission without discarding", () => {
    const {on,input,rec} = begin(); rec.say([["Keep this",true]]); vi.advanceTimersByTime(7000);
    input.setEndpointMs(0); vi.advanceTimersByTime(60000); expect(on.onFinal).not.toHaveBeenCalled();
    input.setEndpointMs(12000); vi.advanceTimersByTime(11999); expect(on.onFinal).not.toHaveBeenCalled();
    input.finish(); expect(on.onFinal).toHaveBeenCalledExactlyOnceWith("Keep this");
  });
  it("errors never submit and fence late ends", () => {
    const {on,rec} = begin(); rec.say([["Do not submit",true]]); rec.onerror?.({error:"network"});
    rec.onend?.(); vi.advanceTimersByTime(20000); expect(on.onFinal).not.toHaveBeenCalled();
    expect(on.onError).toHaveBeenCalledWith("network"); expect(on.onEnd).toHaveBeenCalledOnce();
  });
  it("no-speech rollover retains manual draft without error or automatic submission", () => {
    const {on,input,rec}=begin({endpointMs:0}); rec.say([["Keep thinking",true]]);
    rec.onerror?.({error:"no-speech"}); rec.onend?.(); vi.advanceTimersByTime(100);
    const next=FakeRecognition.last; expect(next).not.toBe(rec);
    next.say([["and continue",true]]); input.finish();
    expect(on.onError).not.toHaveBeenCalled();
    expect(on.onFinal).toHaveBeenCalledExactlyOnceWith("Keep thinking and continue");
  });
  it("backs off repeated quiet recognition ends", () => {
    const {rec}=begin({endpointMs:0}); rec.onend?.(); vi.advanceTimersByTime(100);
    const next=FakeRecognition.last; next.onend?.(); vi.advanceTimersByTime(199);
    expect(FakeRecognition.last).toBe(next); vi.advanceTimersByTime(1);
    expect(FakeRecognition.last).not.toBe(next);
  });
  it("does not endpoint interim results while speech is still active", () => {
    const {on,rec}=begin(); rec.onspeechstart?.(); rec.say([["A long thought",false]]);
    vi.advanceTimersByTime(20000); expect(on.onFinal).not.toHaveBeenCalled();
    rec.onspeechend?.(); vi.advanceTimersByTime(8000);
    expect(on.onFinal).toHaveBeenCalledExactlyOnceWith("A long thought");
  });
  it("handles unsupported and failed starts", () => {
    const on=events(); createVoiceInput(null).start(on); expect(on.onError).toHaveBeenCalledWith("not-supported");
    class Broken extends FakeRecognition { start=vi.fn(()=>{throw Error("failed");}); }
    const broken=events(); createVoiceInput(Broken as unknown as RecognitionCtor).start(broken);
    expect(broken.onError).toHaveBeenCalledWith("start"); expect(broken.onEnd).toHaveBeenCalledOnce();
    expect(recognitionCtor({webkitSpeechRecognition:Ctor})).toBe(Ctor);
  });
});

describe("voiceError", () => {
  it("ticho a vlastní stop jsou bez hlášky, nepovolený mikrofon tlačítko zakáže, síť jen hlásí", () => {
    expect(voiceError("no-speech")).toBeNull();
    expect(voiceError("aborted")).toBeNull();
    expect(voiceError("not-allowed")).toMatchObject({ blocked: true });
    expect(voiceError("not-allowed")!.text).toContain("Mikrofon není povolený");
    expect(voiceError("network")).toMatchObject({ blocked: false });
    expect(voiceError("cokoli")!.text).toMatch(/napiš/);
  });
});
