/**
 * Hlasy Pletora z backendu (`GET /api/pletor/voices`): XTTS (lokální GPU), ElevenLabs (placený cloud), Edge
 * (cloud Microsoftu), Piper (lokální CPU) a prohlížeč jako poslední záloha. Pořadí enginů je zároveň výchozí
 * volba a řetězec záloh: nejlepší dostupný hlas čte, a když jeho engine selže, větu přečte další engine v pořadí.
 * Zvolený lokální hlas nikdy nepadá do cloudu: text, který měl zůstat v počítači, neodejde ani při výpadku.
 */
import { api } from "@/shared/types/logic/types";

export type Engine = "xtts" | "elevenlabs" | "edge" | "piper";
export type Quota = { tier: string | null; character_count: number | null; character_limit: number | null };
export type ServerVoice = {
  id: string; label: string; gender: "male" | "female"; engine: Engine; available: boolean; reason: string | null;
  quota?: Quota | null;
};

export const BROWSER_VOICE = "browser";
export const ENGINES: { id: Engine; label: string }[] = [
  { id: "xtts", label: "XTTS · lokální GPU" },
  { id: "elevenlabs", label: "cloud · ElevenLabs · text opouští počítač" },
  { id: "edge", label: "Edge · cloud · Microsoft · text opouští počítač" },
  { id: "piper", label: "Piper · lokální CPU" },
];
const ORDER = ENGINES.map((engine) => engine.id);
const CLOUD: Engine[] = ["elevenlabs", "edge"];
const LEGACY_ELEVEN = "elevenlabs:voice";
/** Text pro tento engine opouští počítač (štítek „cloud“ v nastavení), jinak zůstává lokálně. */
export const isCloud = (engine: Engine) => CLOUD.includes(engine);

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

/** Hlas ke čtení, nebo `null` = prohlížeč. Bez volby (nebo s nedostupným hlasem) nejlepší dostupný podle pořadí;
 *  za nedostupný lokální hlas jen jiný lokální. */
export function chosenVoice(pref: string | null, voices: ServerVoice[]): string | null {
  if (pref === BROWSER_VOICE) return null;
  // Stará volba z doby jediného hlasu ElevenLabs: vlastní hlas z `.env`, jinak Brian.
  if (pref === LEGACY_ELEVEN) pref = voices.some((voice) => voice.id === "elevenlabs:custom") ? "elevenlabs:custom" : "elevenlabs:brian";
  const saved = voices.find((voice) => voice.id === pref);
  const localOnly = !!saved && !CLOUD.includes(saved.engine);
  const usable = voices.filter((voice) => voice.available && !(localOnly && CLOUD.includes(voice.engine)));
  return usable.find((voice) => voice.id === pref)?.id ?? usable[0]?.id ?? null;
}

/** Zvolený hlas a za ním po jednom dostupném hlasu z každého dalšího enginu v pořadí (raději stejný rod).
 *  Za lokálním hlasem jen lokální enginy, za cloudovým další cloud a nakonec lokální. Prázdný = prohlížeč. */
export function voiceChain(chosen: string | null, voices: ServerVoice[]): string[] {
  const first = voices.find((voice) => voice.id === chosen);
  if (!first) return [];
  const local = !CLOUD.includes(first.engine);
  const engines = ORDER.slice(ORDER.indexOf(first.engine) + 1).filter((engine) => !local || !CLOUD.includes(engine));
  const later = engines.map((engine) => {
    const usable = voices.filter((voice) => voice.engine === engine && voice.available);
    return (usable.find((voice) => voice.gender === first.gender) ?? usable[0])?.id;
  });
  return [first.id, ...later.filter((id): id is string => !!id)];
}

/** Hlasy po skupinách enginů pro výběr v okně; prázdné skupiny vynechá. Kvóta ElevenLabs je jedna za účet, proto
 *  stojí jednou v popisku skupiny, ne u každého hlasu. */
export function voiceGroups(voices: ServerVoice[]) {
  return ENGINES.map((engine) => {
    const members = voices.filter((voice) => voice.engine === engine.id);
    const left = quotaText(members.find((voice) => voice.quota)?.quota);
    return { ...engine, label: left ? `${engine.label} · ${left}` : engine.label, voices: members };
  }).filter((group) => group.voices.length);
}

/** Zbývající znaky tarifu („zbývá 8 400 znaků“, pod 10 % s varováním), bez kvóty `null`. */
function quotaText(quota: Quota | null | undefined): string | null {
  const { character_count: used, character_limit: limit } = quota ?? {};
  if (typeof used !== "number" || typeof limit !== "number" || limit <= 0) return null;
  const left = Math.max(0, limit - used);
  const text = `zbývá ${left.toLocaleString("cs-CZ")} znaků`;
  return left < limit / 10 ? `pozor, ${text}` : text;
}

/** Popisek hlasu ve výběru: nedostupný s poznámkou. */
export function voiceLabel(voice: ServerVoice): string {
  return voice.available ? voice.label : `${voice.label} (nedostupný)`;
}

/** Tooltip hlasu: proč nejde, jinak tarif a spotřeba ElevenLabs. */
export function voiceTitle(voice: ServerVoice): string | undefined {
  if (voice.reason) return voice.reason;
  const quota = voice.quota;
  return quota && typeof quota.character_limit === "number"
    ? `tarif ${quota.tier ?? "?"} · ${(quota.character_count ?? 0).toLocaleString("cs-CZ")} / ${quota.character_limit.toLocaleString("cs-CZ")} znaků tento měsíc`
    : undefined;
}