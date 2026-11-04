import { describe, expect, it } from "vitest";
import { BROWSER_VOICE, chosenVoice, parseVoices, voiceChain, voiceGroups, voiceLabel, voiceTitle, type ServerVoice } from "./tts-voices";

const voice = (id: string, engine: ServerVoice["engine"], gender: ServerVoice["gender"], available = true): ServerVoice =>
  ({ id, label: id, gender, engine, available, reason: available ? null : "nedostupný" });

const XTTS = voice("xtts:default", "xtts", "male");
const ELEVEN = voice("elevenlabs:voice", "elevenlabs", "male");
const ANTONIN = voice("edge:cs-CZ-AntoninNeural", "edge", "male");
const VLASTA = voice("edge:cs-CZ-VlastaNeural", "edge", "female");
const JIRKA = voice("cs_CZ-jirka-medium", "piper", "male");
const KASANDRA = voice("cs_CZ-kasandra-medium", "piper", "female");

describe("parseVoices", () => {
  it("bere jen platné hlasy známých enginů a řadí XTTS → Edge → Piper", () => {
    expect(parseVoices({ voices: [JIRKA, { id: 1 }, VLASTA, { ...XTTS, engine: "gpt" }, XTTS] })).toEqual([XTTS, VLASTA, JIRKA]);
    expect(parseVoices(null)).toEqual([]);
    expect(parseVoices({ available: [JIRKA], default: JIRKA.id })).toEqual([]); // starý tvar backendu
  });
});

describe("chosenVoice", () => {
  it("ElevenLabs je druhý v pořadí, ale jen když je ověřeně dostupný", () => {
    expect(chosenVoice(null, [{ ...XTTS, available: false }, ELEVEN, ANTONIN])).toBe(ELEVEN.id);
    expect(chosenVoice(null, [{ ...XTTS, available: false }, { ...ELEVEN, available: false }, ANTONIN])).toBe(ANTONIN.id);
  });
  it("za nedostupný lokální hlas jen jiný lokální, nikdy cloud", () => {
    expect(chosenVoice(JIRKA.id, [{ ...XTTS, available: false }, ELEVEN, ANTONIN, { ...JIRKA, available: false }, KASANDRA]))
      .toBe(KASANDRA.id);
    expect(chosenVoice(JIRKA.id, [ELEVEN, ANTONIN, { ...JIRKA, available: false }])).toBeNull();
  });
  it("bez volby nejlepší dostupný: XTTS, jinak Edge, jinak Piper, jinak prohlížeč", () => {
    const all = [XTTS, ANTONIN, VLASTA, JIRKA];
    expect(chosenVoice(null, all)).toBe(XTTS.id);
    expect(chosenVoice(null, [{ ...XTTS, available: false }, ANTONIN, JIRKA])).toBe(ANTONIN.id);
    expect(chosenVoice(null, [{ ...XTTS, available: false }, { ...ANTONIN, available: false }, JIRKA])).toBe(JIRKA.id);
    expect(chosenVoice(null, [{ ...JIRKA, available: false }])).toBeNull();
  });
  it("uložená volba platí, dokud je dostupná; Prohlížeč vždy", () => {
    expect(chosenVoice(VLASTA.id, [XTTS, VLASTA])).toBe(VLASTA.id);
    expect(chosenVoice(VLASTA.id, [XTTS, { ...VLASTA, available: false }])).toBe(XTTS.id);
    expect(chosenVoice(BROWSER_VOICE, [XTTS])).toBeNull();
  });
});

describe("voiceChain", () => {
  it("za zvoleným hlasem po jednom z dalších enginů, raději stejný rod; lokální nikdy do cloudu", () => {
    const all = [XTTS, ELEVEN, ANTONIN, VLASTA, JIRKA, KASANDRA];
    expect(voiceChain(XTTS.id, all)).toEqual([XTTS.id, JIRKA.id]);
    expect(voiceChain(ELEVEN.id, all)).toEqual([ELEVEN.id, ANTONIN.id, JIRKA.id]);
    expect(voiceChain(VLASTA.id, all)).toEqual([VLASTA.id, KASANDRA.id]);
    expect(voiceChain(JIRKA.id, all)).toEqual([JIRKA.id]);
    expect(voiceChain(XTTS.id, [XTTS, ANTONIN, { ...JIRKA, available: false }, KASANDRA])).toEqual([XTTS.id, KASANDRA.id]);
    expect(voiceChain(null, all)).toEqual([]);
  });
});

describe("voiceGroups", () => {
  it("seskupí hlasy podle enginu v pořadí a vynechá prázdné skupiny", () => {
    const groups = voiceGroups([JIRKA, XTTS, KASANDRA]);
    expect(groups.map((group) => [group.id, group.voices.map((item) => item.id)])).toEqual([
      ["xtts", [XTTS.id]], ["piper", [JIRKA.id, KASANDRA.id]]]);
    expect(voiceGroups([ANTONIN])[0].label).toMatch(/text opouští počítač/);
  });
});

describe("voiceLabel / voiceTitle", () => {
  const quota = (used: number) => ({ ...ELEVEN, quota: { tier: "free", character_count: used, character_limit: 10000 } });
  it("ElevenLabs ukáže zbývající znaky, pod 10 % s varováním; nedostupný s důvodem v tooltipu", () => {
    expect(voiceLabel(quota(1600)).replace(/\s/g, " ")).toBe("elevenlabs:voice · zbývá 8 400 znaků");
    expect(voiceLabel(quota(9500)).replace(/\s/g, " ")).toBe("elevenlabs:voice · pozor, zbývá 500 znaků");
    expect(voiceLabel(ANTONIN)).toBe(ANTONIN.id);
    const denied = { ...quota(0), available: false, reason: "hlas Pletor_MH vyžaduje tarif Creator" };
    expect(voiceLabel(denied)).toBe("elevenlabs:voice (nedostupný)");
    expect(voiceTitle(denied)).toBe("hlas Pletor_MH vyžaduje tarif Creator");
    expect(voiceTitle(quota(1600))?.replace(/\s/g, " ")).toBe("tarif free · 1 600 / 10 000 znaků tento měsíc");
    expect(voiceTitle(JIRKA)).toBeUndefined();
  });
});