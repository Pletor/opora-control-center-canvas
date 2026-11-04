/**
 * Preference hlasu okna Pletor jsou volba aplikace, ne projektu: jeden klíč pro všechny projekty.
 * `conversation`: po domluvení se mikrofon sám znovu zapne (jinak „push“: jedna věta a konec).
 * `voice`: odpovědi se čtou nahlas i na psané zprávy.
 */
export const VOICE_PREFS_KEY = "opora:pletor:voice:v1";

export type VoicePrefs = { conversation: boolean; voice: boolean };
export const DEFAULT_VOICE_PREFS: VoicePrefs = { conversation: false, voice: false };

export function parseVoicePrefs(raw: string | null): VoicePrefs {
  try {
    const value = JSON.parse(raw ?? "null");
    if (value && typeof value === "object") return { conversation: value.conversation === true, voice: value.voice === true };
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
