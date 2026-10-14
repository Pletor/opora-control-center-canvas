// Zadání pro agenta-rozkladače sektoru (o úroveň níž než oblast: sektor → karty). Čistá funkce bez
// Reactu; inspektor sektoru jen ukáže výsledek. Název, podstata a počet karet jdou do zadání jen jako
// citovaná data z chvíle kopírování; cíl, akceptaci a bránu sektoru agent čte sám z `node-brief --raw`,
// aby pracoval s aktuálním stavem, ne s kopií. Tvar dávky drží `references/canvas-plan.md`.
import { dataBlock, oneLine, quoted, safeIds } from "@/shared/agent-prompt/logic/agent-prompt";

export type SectorDecomposeInput = {
  project: string;
  workspace: string;
  sectorId: string;
  sectorName: string;
  /** Podstata sektoru (`node.purpose`), jak byla uložená při kopírování. */
  purpose: string;
  /** Kolik karet už v sektoru leží; rozkladač je nemění, jen pokryje zbytek cíle. */
  cards: number;
};

/** Hotové zadání pro rozkladače sektoru, nebo `null`, když identifikátor (projekt, workspace, sektor) neprojde. */
export function sectorDecomposePrompt({ project, workspace, sectorId, sectorName, purpose, cards }: SectorDecomposeInput): string | null {
  if (!safeIds(project, workspace, sectorId)) return null;
  return [
    "/opora-control-center",
    `Jsi rozkladač sektoru. Projekt ${project}, workspace ${workspace}, sektor id ${sectorId}. Postupuj podle references/rozklad.md, oddíl „Sektor → karty“.`,
    ...dataBlock("Sektor", [
      `Název sektoru: ${oneLine(sectorName)}`,
      `Podstata sektoru: ${quoted(purpose.trim()) || "(nevyplněná)"}`,
      `Počet karet v sektoru: ${cards}`,
    ]),
    `Cíl, mimo rozsah, akceptaci, pravidla a bránu sektoru čti z \`opora_read.py node-brief --node ${sectorId} --raw\`, karty sektoru z \`view --raw\`; když se od kopie výše liší, nic nezapisuj a vrať blokaci.`,
    "Porovnej cíl a akceptaci sektoru s existujícími kartami a navrhuj jen nepokrytou část: 1–9 karet, obvykle 3–7. Když nic nechybí, nebo chybí vstup, dávku nestav a vrať jeden souhrn.",
    `Dávka \`/api/canvas-plan\`: každá karta s \`parent: "@${sectorId}"\`, předponou [task] / [research] / [prototype], purpose, spec {goal, non_goals, acceptance}, bloky s condition a porty, sourceRef, checks u karty s testy; vazby next / block mezi kartami a na kartu [gate] sektoru. Kartu [gate] ani existující karty neměň; proces kartám pak určí router.`,
    "Nejdřív `--dry-run`; ke schválení ukaž celou dávku (u každé karty název, účel, cíl, akceptaci, bloky s porty a vazby). Souhlas platí jen pro přesně ten soubor a digest; ostře zapiš až po něm.",
  ].join("\n");
}
