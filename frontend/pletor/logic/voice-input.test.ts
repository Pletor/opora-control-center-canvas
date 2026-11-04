import { describe, expect, it, vi } from "vitest";
import { createVoiceInput, recognitionCtor, voiceError, type RecognitionCtor, type VoiceInputEvents } from "./voice-input";

/** Falešné SpeechRecognition: zapamatuje si poslední instanci, test pak sám posílá výsledky a konec. */
class FakeRecognition {
  static last: FakeRecognition;
  lang = ""; interimResults = false; continuous = true; maxAlternatives = 0;
  onspeechstart: (() => void) | null = null;
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

describe("createVoiceInput", () => {
  it("poslouchá česky jednu větu s průběžným přepisem", () => {
    createVoiceInput(Ctor).start(events());
    const rec = FakeRecognition.last;
    expect([rec.lang, rec.interimResults, rec.continuous]).toEqual(["cs-CZ", true, false]);
    expect(rec.start).toHaveBeenCalledOnce();
  });

  it("průběžný text hlásí, finální větu pošle právě jednou (auto-odeslání)", () => {
    const on = events();
    createVoiceInput(Ctor).start(on);
    const rec = FakeRecognition.last;
    rec.onspeechstart?.();
    rec.say([["Postav", false]]);
    rec.say([["Postav web ", true]]);
    rec.say([["Postav web znovu", true]]);
    rec.onend?.();
    expect(on.onSpeech).toHaveBeenCalledOnce();
    expect(on.onInterim).toHaveBeenCalledWith("Postav");
    expect(on.onFinal).toHaveBeenCalledTimes(1);
    expect(on.onFinal).toHaveBeenCalledWith("Postav web");
    expect(on.onEnd).toHaveBeenCalledOnce();
  });

  it("trvalý poslech pošle každou novou hotovou větu jednou", () => {
    const on = events();
    createVoiceInput(Ctor).start(on, { continuous: true });
    const rec = FakeRecognition.last;
    expect(rec.continuous).toBe(true);
    rec.say([["první", true]]);
    rec.say([["první", true], ["dru", false]]);
    rec.say([["první", true], ["druhá věta", true]]);
    expect(on.onFinal).toHaveBeenNthCalledWith(1, "první");
    expect(on.onFinal).toHaveBeenNthCalledWith(2, "druhá věta");
    expect(on.onFinal).toHaveBeenCalledTimes(2);
    expect(on.onInterim).toHaveBeenCalledWith("dru");
  });

  it("stop poslech utne a starý poslech už nic nehlásí", () => {
    const on = events();
    const input = createVoiceInput(Ctor);
    input.start(on);
    const rec = FakeRecognition.last;
    input.stop();
    rec.say([["pozdě", true]]);
    expect(rec.abort).toHaveBeenCalledOnce();
    expect(on.onFinal).not.toHaveBeenCalled();
    expect(on.onEnd).not.toHaveBeenCalled();
  });

  it("chybu předá kódem; start, který spadne, okno neshodí", () => {
    const on = events();
    createVoiceInput(Ctor).start(on);
    FakeRecognition.last.onerror?.({ error: "not-allowed" });
    expect(on.onError).toHaveBeenCalledWith("not-allowed");
    class Broken extends FakeRecognition { start = vi.fn(() => { throw new Error("už běží"); }); }
    const broken = events();
    expect(() => createVoiceInput(Broken as unknown as RecognitionCtor).start(broken)).not.toThrow();
    expect(broken.onError).toHaveBeenCalledWith("start");
    expect(broken.onEnd).toHaveBeenCalledOnce();
  });

  it("bez rozpoznávání řeči (Firefox) není podporováno", () => {
    expect(recognitionCtor({})).toBeNull();
    expect(recognitionCtor({ webkitSpeechRecognition: Ctor })).toBe(Ctor);
    const input = createVoiceInput(null);
    const on = events();
    input.start(on);
    expect(input.supported).toBe(false);
    expect(on.onError).toHaveBeenCalledWith("not-supported");
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
