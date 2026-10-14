// Zadání pro agenta-rozkladače: ze záměru oblasti udělá jeden text ke zkopírování do terminálu se
// skillem `/opora-control-center`. Čistá funkce bez Reactu; inspektor oblasti jen ukáže výsledek.
// Název, záměr a počet sektorů jdou do zadání jen jako citovaná data (kopie z chvíle kopírování);
// pravdu o oblasti agent čte z `view`. Tvar dávky drží `references/canvas-plan.md`: nový uzel s
// `parent: "@<id oblasti>"` backend položí na vrstvu oblasti do jejího rámečku. Identifikátory se
// ověří (`safeIds`), volný text jde jen do datového bloku (`dataBlock`).
import { dataBlock, oneLine, quoted, safeIds } from "@/shared/agent-prompt/logic/agent-prompt";

export type DecomposeInput = {
  project: string;
  workspace: string;
  areaId: string;
  areaName: string;
  intent: string;
  /** Kolik sektorů v oblasti leželo při kopírování; rozkladač je nesmí měnit, jen pokrýt zbytek záměru. */
  sectors: number;
};

/** Hotové zadání pro rozkladače, nebo `null`, když oblast nemá záměr nebo identifikátor neprojde. */
export function decomposePrompt({ project, workspace, areaId, areaName, intent, sectors }: DecomposeInput): string | null {
  const text = intent.trim();
  if (!text || !safeIds(project, workspace, areaId)) return null;
  return [
    "/opora-control-center",
    `Jsi rozkladač oblasti. Projekt ${project}, workspace ${workspace}, oblast id ${areaId}. Postupuj podle references/rozklad.md.`,
    ...dataBlock("Záměr", [
      `Název oblasti: ${oneLine(areaName)}`,
      `Záměr oblasti: ${quoted(text)}`,
      `Počet sektorů v oblasti: ${sectors}`,
    ]),
    "Aktuální název, záměr a sektory oblasti ber z `opora_read.py view --raw`; když se od kopie výše liší, nic nezapisuj a vrať blokaci.",
    "Před návrhem načti profil a pravidla projektu a porovnej záměr s účelem a akceptací existujících sektorů; navrhuj jen nepokrytou část: 1–7 sektorů, obvykle 2–5. Když stačí 0–1 sektor, nebo chybí vstup (profil, pravidla, mapa kódu), dávku nestav a vrať jeden souhrn.",
    `Dávka \`/api/canvas-plan\`: každý sektor s \`parent: "@${areaId}"\` (backend ho položí dovnitř rámečku oblasti) a jednou kartou [gate] s \`parent\` = ref sektoru; jiné karty nezakládej a existující sektory neměň.`,
    "Nejdřív `--dry-run`; ke schválení ukaž celou dávku (u každého sektoru název, účel, cíl, akceptaci a bránu). Souhlas platí jen pro přesně ten soubor a digest; ostře zapiš až po něm.",
  ].join("\n");
}
