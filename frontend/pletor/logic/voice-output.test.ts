import { describe, expect, it, vi } from "vitest";
import { createVoiceOutput, pickVoice, speechLevel, splitSentences, type UtteranceCtor } from "./voice-output";
import { parseVoicePrefs } from "./voice-prefs";

type Spoken = { text: string; lang: string; voice: unknown; rate: number; pitch: number; onboundary: (() => void) | null; onend: (() => void) | null; onerror: (() => void) | null };

/** Falešné speechSynthesis: fronta promluv; test je dokončuje ručně (`finish`). */
function fakeSynth(voices: { name: string; lang: string }[] = []) {
  const spoken: Spoken[] = [];
  const synth = { speak: vi.fn((u: Spoken) => spoken.push(u)), cancel: vi.fn(), getVoices: () => voices };
  const Utterance = function (this: Spoken, text: string) { this.text = text; } as unknown as UtteranceCtor;
  const finish = () => spoken[spoken.length - 1].onend?.();
  return { synth, Utterance, spoken, finish };
}

describe("splitSentences", () => {
  it("dělí na věty a dlouhou větu po slovech", () => {
    expect(splitSentences("Ahoj. Jak se máš? Dobře!")).toEqual(["Ahoj.", "Jak se máš?", "Dobře!"]);
    expect(splitSentences("Schůzka je v 10.30 dnes.")).toEqual(["Schůzka je v 10.30 dnes."]);
    const long = splitSentences(`${"slovo ".repeat(60)}konec.`, 50);
    expect(long.length).toBeGreaterThan(1);
    expect(long.every((part) => part.length <= 50)).toBe(true);
  });
  it("markdown nečte nahlas", () => {
    expect(splitSentences("**Pozor** na `kód`.")).toEqual(["Pozor na kód ."]);
    expect(splitSentences("   ")).toEqual([]);
  });
});

describe("pickVoice", () => {
  it("nejdřív český Google/Microsoft, pak první český, jinak výchozí", () => {
    const zuzana = { name: "Zuzana", lang: "cs-CZ" };
    const jakub = { name: "Microsoft Jakub - Czech", lang: "cs-CZ" };
    expect(pickVoice([{ name: "Google US English", lang: "en-US" }, zuzana, jakub])).toBe(jakub);
    expect(pickVoice([{ name: "Daniel", lang: "en-GB" }, zuzana])).toBe(zuzana);
    expect(pickVoice([{ name: "Daniel", lang: "en-GB" }])).toBeNull();
  });
});

describe("createVoiceOutput", () => {
  it("čte větu po větě českým hlasem, rychlost ~1, výška ~0.9, a ohlásí domluvení", () => {
    const jakub = { name: "Microsoft Jakub", lang: "cs-CZ" };
    const { synth, Utterance, spoken, finish } = fakeSynth([jakub]);
    const onEnd = vi.fn(), onBoundary = vi.fn();
    createVoiceOutput(synth, Utterance).speak("První věta. Druhá věta.", { onEnd, onBoundary });
    expect(spoken.map((u) => u.text)).toEqual(["První věta."]);
    expect(spoken[0]).toMatchObject({ voice: jakub, lang: "cs-CZ" });
    expect(spoken[0].rate).toBeGreaterThanOrEqual(1);
    expect(spoken[0].rate).toBeLessThanOrEqual(1.05);
    expect(spoken[0].pitch).toBeCloseTo(0.9);
    spoken[0].onboundary?.();
    expect(onBoundary).toHaveBeenCalledOnce();
    finish();
    spoken[0].onerror?.(); // end i error téže věty: dál se jde jen jednou
    expect(spoken.map((u) => u.text)).toEqual(["První věta.", "Druhá věta."]);
    expect(onEnd).not.toHaveBeenCalled();
    finish();
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it("barge-in: stop okamžitě zruší syntézu a zbytek odpovědi už nečte", () => {
    const { synth, Utterance, spoken, finish } = fakeSynth();
    const onEnd = vi.fn();
    const output = createVoiceOutput(synth, Utterance);
    output.speak("Jedna. Dvě. Tři.", { onEnd });
    output.stop();
    expect(synth.cancel).toHaveBeenCalled();
    finish(); // prohlížeč po cancel pošle konec přerušené věty
    expect(spoken).toHaveLength(1);
    expect(onEnd).not.toHaveBeenCalled();
  });

  it("bez syntézy řeči nic nečte, jen ohlásí konec", () => {
    const onEnd = vi.fn();
    const output = createVoiceOutput(null, null);
    output.speak("Ahoj.", { onEnd });
    expect(output.supported).toBe(false);
    expect(onEnd).toHaveBeenCalledOnce();
  });
});

describe("speechLevel a preference", () => {
  it("slovo pulzne jádrem a puls doznívá", () => {
    expect(speechLevel(1000, 1000)).toBeGreaterThan(speechLevel(1400, 1000) + 0.4);
  });
  it("preference hlasu jsou jen dvě pravdivostní volby, poškozené = výchozí", () => {
    expect(parseVoicePrefs('{"conversation":true,"voice":1}')).toEqual({ conversation: true, voice: false });
    expect(parseVoicePrefs("{")).toEqual({ conversation: false, voice: false });
  });
});
