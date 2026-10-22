// Tón karty pro souhrny (hlava sektoru na plátně, Velín): šest tónů se značkou a slovem. Odvozuje se
// z tváře karty, aby plátno i Velín počítaly stejně.
import type { CardFace, FaceState } from "./card-face";

export type PillTone = "ok" | "run" | "gate" | "human" | "bad" | "blocked";
export type Counts = Record<PillTone, number>;
export const TONES: PillTone[] = ["ok", "run", "gate", "human", "bad", "blocked"];
export const TONE_GLYPH: Record<PillTone, string> = { ok: "✓", run: "▸", gate: "◷", human: "●", bad: "✕", blocked: "○" };
export const TONE_LABEL: Record<PillTone, string> = { ok: "v pořádku", run: "agent pracuje", gate: "čeká na bránu / review",
  human: "čeká na tebe", bad: "problém", blocked: "blokováno předchůdcem" };
const TONE_OF: Record<FaceState, PillTone> = { done: "ok", ready: "ok", plan: "ok", working: "run", review: "gate",
  decision: "human", problem: "bad", blocked: "blocked" };

export function toneOf(face: CardFace): PillTone {
  if (face.state === "review" && face.chip.tone === "bad") return "bad";
  if (face.state === "plan" && face.chip.tone === "warn") return "gate";
  return TONE_OF[face.state];
}
export const zeroCounts = (): Counts => ({ ok: 0, run: 0, gate: 0, human: 0, bad: 0, blocked: 0 });
export function countTones(faces: readonly CardFace[]): Counts {
  const counts = zeroCounts();
  for (const face of faces) counts[toneOf(face)] += 1;
  return counts;
}
