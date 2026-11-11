// Odvozené značky boxu na plátně 2 (docs/navrhy/2026-11-10-platno-2.md, Verze 3 „Stavy boxu“): skica, počet inspirací,
// počet prvků logiky a jejich nejhorší milník, Ověřeno a čárkovaný rám návrhu. Nic se neukládá. Bez Reactu, test vedle.
import type { CanvasNode, PageSection } from "@/shared/types/logic/types";
import type { StudioState } from "@/project/studio/logic/studio-status";
import { DONE_COUNT, type Milestone } from "../../logic/plan-progress";

export type BoxBadges = {
  sketch: boolean; inspirations: number; logic: number;
  /** Milník, na kterém stojí nejpomalejší prvek boxu; `null` = box nemá prvky nebo jsou všechny ověřené. */
  worst: Milestone["label"] | null;
  /** Box má prvky a všechny jsou ověřené. */
  verified: boolean;
  proposed: boolean;
};

const LABELS: Milestone["label"][] = ["Návrh", "Realizace", "Ověření"];

export function boxBadges(section: Pick<PageSection, "status" | "inspiration">, nodes: readonly CanvasNode[],
  states: ReadonlyMap<string, { state: StudioState }>, sketched: boolean): BoxBadges {
  const least = Math.min(...nodes.map((node) => DONE_COUNT[states.get(node.id)?.state ?? "plan"]));
  const verified = nodes.length > 0 && least === DONE_COUNT.verified;
  return { sketch: sketched, inspirations: (section.inspiration?.files?.length ?? 0) + (section.inspiration?.url ? 1 : 0), logic: nodes.length,
    worst: nodes.length && !verified ? LABELS[least] : null, verified, proposed: section.status === "proposed" };
}
