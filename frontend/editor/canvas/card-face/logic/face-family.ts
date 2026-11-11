// Druh, kód, stavová pilulka a počitadlo karty na plátně 3 (návrh „Neonový dashboard OPORA: Editor“). Nic se
// nevymýšlí: druh je předpona v názvu (`[research] ` …, týž `effectiveType` jako backend `cards[].kind`) nebo
// doménová role `element.kind`; kód je písmeno druhu a pořadí podle záměru (`cards[].order`), jinak začátek id.
import type { CardType, ElementKind } from "@/shared/types/logic/types";
import type { CardFace } from "./card-face";

/** Rodina = barva rámu: pracovní krok fialově, kontrakt zeleně, ověření šeříkově, rozhodnutí oranžovým kosočtvercem. */
export type FaceFamily = "work" | "contract" | "verify" | "decision";
export type FaceKind = { family: FaceFamily; word: string; code: string };

const BY_TYPE: Record<CardType, [FaceFamily, string]> = {
  research: ["work", "Výzkum"], prototype: ["work", "Návrh"], task: ["work", "Úkol"],
  gate: ["verify", "Ověření"], grilling: ["decision", "Rozhodnutí"],
};
const BY_ELEMENT: Partial<Record<ElementKind, [FaceFamily, string]>> = {
  api_contract: ["contract", "Kontrakt"], condition: ["decision", "Rozhodnutí"],
};
const LETTER: Record<FaceFamily, string> = { work: "E", contract: "C", verify: "V", decision: "R" };

export function faceKind({ nodeId, type, element, sector, order }: {
  nodeId: string; type: CardType | null; element?: ElementKind; sector: boolean; order?: number | null;
}): FaceKind {
  const [family, word] = (type && BY_TYPE[type]) || (element && BY_ELEMENT[element]) || ["work", sector ? "Sektor" : "Krok"];
  // shortcut: bez pořadí je číslo začátek id (stabilní, ale nečitelné); až srdce zapíše pořadí všem kartám, zmizí.
  const number = order != null ? String(order) : nodeId.replace(/[^a-z0-9]/gi, "").slice(0, 4).toUpperCase();
  return { family, word, code: `${LETTER[family]}-${number}` };
}

export type PillTone = "done" | "run" | "wait" | "ready" | "prep" | "bad";
const PILL: Record<CardFace["state"], [PillTone, string]> = {
  done: ["done", "Hotovo"], working: ["run", "V realizaci"], review: ["run", "Na kontrole"], decision: ["wait", "Čeká na tebe"],
  blocked: ["wait", "Čeká"], ready: ["ready", "Přijatý"], plan: ["prep", "V přípravě"], problem: ["bad", "Problém"],
};

/** Jedno slovo stavu podle návrhu; podrobný důvod zůstává v titulku pilulky. */
export function facePill(face: CardFace): { tone: PillTone; word: string } {
  const [tone, word] = PILL[face.state];
  return { tone, word };
}

const krok = (n: number) => (n === 1 ? "krok" : n >= 2 && n <= 4 ? "kroky" : "kroků");
/** „2/4 kroky“; karta bez kroků počitadlo nemá (žádná falešná nula). */
export function faceCounter(face: CardFace): string {
  const { done, total } = face.steps;
  return total ? `${done}/${total} ${krok(total)}` : "";
}
