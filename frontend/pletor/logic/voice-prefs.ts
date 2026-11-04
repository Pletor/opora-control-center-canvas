/**
 * Preference hlasu okna Pletor jsou volba aplikace, ne projektu: jeden klíč pro všechny projekty.
 * `conversation`: po domluvení se mikrofon sám znovu zapne (jinak „push“: jedna věta a konec).
 * `bargeIn`: v Poslechu řeč člověka utne čtení odpovědi (výchozí zapnuto; bez sluchátek lze vypnout).
 * `voice`: odpovědi se čtou nahlas i na psané zprávy.
 * `ttsVoice` (P3b): id hlasu serveru (`xtts:default`, `elevenlabs:brian`, `edge:cs-CZ-AntoninNeural`,
 * `cs_CZ-jirka-medium`…), `browser` = prohlížeč, `null` = nejlepší dostupný (XTTS → ElevenLabs → Edge → Piper).
 * Stará volba `elevenlabs:voice` zůstává uložená a `chosenVoice` ji čte jako vlastní hlas, jinak Briana.
 */
export const VOICE_PREFS_KEY = "opora:pletor:voice:v1";

export type VoicePrefs = { conversation: boolean; voice: boolean; ttsVoice: string | null; bargeIn: boolean };
export const DEFAULT_VOICE_PREFS: VoicePrefs = { conversation: false, voice: false, ttsVoice: null, bargeIn: true };

export function parseVoicePrefs(raw: string | null): VoicePrefs {
  try {
    const value = JSON.parse(raw ?? "null");
    if (value && typeof value === "object")
      return { conversation: value.conversation === true, voice: value.voice === true,
        ttsVoice: typeof value.ttsVoice === "string" ? value.ttsVoice : null, bargeIn: value.bargeIn !== false };
  } catch {
    /* Poškozené preference nejsou data projektu. */
  }
  return { ...DEFAULT_VOICE_PREFS };
}

export function readVoicePrefs(): VoicePrefs {
  try {
    return parseVoicePrefs(localStorage.getItem(VOICE_PREFS_KEY));
  } catch {
    return { ...DEFAULT_VOICE_PREFS };
  }
}

export function writeVoicePrefs(prefs: VoicePrefs): void {
  try {
    localStorage.setItem(VOICE_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* Bez úložiště volba platí jen do zavření stránky. */
  }
}
