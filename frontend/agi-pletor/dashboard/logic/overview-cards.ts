import { brainLabel, escalationText, heartText, type PletorState } from "@/agi-pletor/hud/logic/pletor-client";
import { BROWSER_VOICE, chosenVoice, type ServerVoice } from "@/agi-pletor/hud/logic/tts-voices";

export type OverviewCard = { id: string; title: string; value: string; note: string };

/** Hlas, kterým se skutečně čte: zvolený (nebo nejlepší dostupný) podle štítků serveru, jinak prohlížeč. */
export function voiceName(pref: string | null, voices: ServerVoice[]): string {
  const id = chosenVoice(pref, voices);
  if (id === null || id === BROWSER_VOICE) return "Prohlížeč";
  return voices.find((voice) => voice.id === id)?.label ?? id;
}

const clip = (text: string, max = 140) => (text.length > max ? text.slice(0, max - 1) + "…" : text);

/** Stav Pletora → karty Přehledu: Mozek, Srdce, Eskalace, Hlas, Poslední zpráva. `state === null` = ještě nenačteno. */
export function overviewCards(state: PletorState | null, voice: string): OverviewCard[] {
  const brain = state ? brainLabel(state.brain) : null;
  const last = state?.messages[state.messages.length - 1];
  return [
    { id: "mozek", title: "Mozek", value: brain?.name ?? "—", note: brain?.plan ?? "načítám" },
    { id: "srdce", title: "Srdce", value: state ? heartText(state.heart) : "—", note: "stav ze serveru" },
    { id: "eskalace", title: "Eskalace", value: state ? escalationText(state.escalations.length) : "—", note: "čeká na člověka" },
    { id: "hlas", title: "Hlas", value: voice, note: "čte odpovědi nahlas" },
    { id: "zprava", title: "Poslední zpráva", value: last ? clip(last.text) : state ? "Zatím bez rozhovoru" : "—",
      note: last ? (last.role === "human" ? "člověk" : "Pletor") : "rozhovor" },
  ];
}
