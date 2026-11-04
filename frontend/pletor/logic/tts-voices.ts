/**
 * Hlasy Pletora z backendu (`GET /api/pletor/voices`): XTTS (lokální GPU), Edge (cloud Microsoftu), Piper
 * (lokální CPU) a prohlížeč jako poslední záloha. Pořadí enginů je zároveň výchozí volba a řetězec záloh:
 * nejlepší dostupný hlas čte, a když jeho engine selže, větu přečte další engine v pořadí.
 */
import { api } from "@/shared/types/logic/types";

export type Engine = "xtts" | "edge" | "piper";
export type ServerVoice = {
  id: string; label: string; gender: "male" | "female"; engine: Engine; available: boolean; reason: string | null;
};

export const BROWSER_VOICE = "browser";
export const ENGINES: { id: Engine; label: string }[] = [
  { id: "xtts", label: "XTTS · lokální GPU" },
  { id: "edge", label: "Edge · cloud · Microsoft · text opouští počítač" },
  { id: "piper", label: "Piper · lokální CPU" },
];
const ORDER = ENGINES.map((engine) => engine.id);

/** Platné hlasy seřazené podle enginu (XTTS → Edge → Piper); neznámý engine se zahodí. */
export function parseVoices(value: unknown): ServerVoice[] {
  const raw = (value && typeof value === "object" ? (value as { voices?: unknown }).voices : null);
  return (Array.isArray(raw) ? raw : [])
    .filter((voice): voice is ServerVoice => !!voice && typeof voice.id === "string" && typeof voice.label === "string"
      && ORDER.includes(voice.engine))
    .map((voice) => ({ ...voice, available: voice.available === true, reason: voice.reason ?? null }))
    .sort((a, b) => ORDER.indexOf(a.engine) - ORDER.indexOf(b.engine));
}

/** Seznam hlasů; `warm` je uložená volba, kterou backend načte dopředu. Nedostupný server = jen prohlížeč. */
export const fetchVoices = (warm: string | null) =>
  api<unknown>(`/api/pletor/voices${warm ? `?warm=${encodeURIComponent(warm)}` : ""}`).then(parseVoices, () => []);

/** Hlas ke čtení, nebo `null` = prohlížeč. Bez volby (nebo s nedostupným hlasem) nejlepší dostupný podle pořadí. */
export function chosenVoice(pref: string | null, voices: ServerVoice[]): string | null {
  if (pref === BROWSER_VOICE) return null;
  const usable = voices.filter((voice) => voice.available);
  return usable.find((voice) => voice.id === pref)?.id ?? usable[0]?.id ?? null;
}

/** Zvolený hlas a za ním po jednom dostupném hlasu z každého dalšího enginu v pořadí (raději stejný rod).
 *  Prázdný = prohlížeč. */
export function voiceChain(chosen: string | null, voices: ServerVoice[]): string[] {
  const first = voices.find((voice) => voice.id === chosen);
  if (!first) return [];
  const later = ORDER.slice(ORDER.indexOf(first.engine) + 1).map((engine) => {
    const usable = voices.filter((voice) => voice.engine === engine && voice.available);
    return (usable.find((voice) => voice.gender === first.gender) ?? usable[0])?.id;
  });
  return [first.id, ...later.filter((id): id is string => !!id)];
}

/** Hlasy po skupinách enginů pro výběr v okně; prázdné skupiny vynechá. */
export function voiceGroups(voices: ServerVoice[]) {
  return ENGINES.map((engine) => ({ ...engine, voices: voices.filter((voice) => voice.engine === engine.id) }))
    .filter((group) => group.voices.length);
}
