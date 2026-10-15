// Zadání pro agenta-rozkladače oblasti: ze záměru oblasti udělá jeden text ke zkopírování do terminálu
// se skillem `/opora-control-center`. Čistá funkce bez Reactu; inspektor oblasti jen ukáže výsledek.
// Oblast má dvě polohy (`docs/pyramida.md` §1): na kořenové vrstvě je téma a rozpadá se na **sektory**;
// uvnitř vrstvy sektoru je **fáze** (① MVP, ② Ladění…) a rozpadá se rovnou na **karty** sektoru, které
// backend položí do jejího rámečku. Žádný třetí druh uzlu kvůli tomu nevzniká. Název, záměr a počty jdou
// do zadání jen jako citovaná data (kopie z chvíle kopírování); pravdu o oblasti agent čte z `view`.
// Tvar dávky drží `references/canvas-plan.md`: nový uzel s `parent: "@<id oblasti>"` backend položí na
// vrstvu oblasti do jejího rámečku. Identifikátory se ověří (`safeIds`), volný text jde jen do `dataBlock`.
import { dataBlock, oneLine, quoted, safeIds } from "@/shared/agent-prompt/logic/agent-prompt";
import type { AreaHost } from "@/editor/canvas/area/logic/area-model";

export type { AreaHost };

export type DecomposeInput = {
  project: string;
  workspace: string;
  areaId: string;
  areaName: string;
  intent: string;
  /** Kolik sektorů v oblasti leželo při kopírování; rozkladač je nesmí měnit, jen pokrýt zbytek záměru. */
  sectors: number;
  /** Kolik karet (`kind: "node"`) v oblasti leželo při kopírování; u fáze sektoru je to pokryté. */
  cards?: number;
  host?: AreaHost | null;
};

/** Jak se oblast rozpadá: téma na kořenové vrstvě na sektory, fáze uvnitř sektoru na karty; oblast ve
 *  vnitřním plátně karty (nebo s rodičem, který v grafu chybí) se nerozkládá. */
export function decomposeTarget(host: AreaHost | null | undefined): "sectors" | "cards" | "none" {
  if (!host) return "sectors";
  return host.kind === "sector" ? "cards" : "none";
}

/** Hotové zadání pro rozkladače, nebo `null`, když oblast nemá záměr nebo identifikátor neprojde. */
export function decomposePrompt({ project, workspace, areaId, areaName, intent, sectors, cards = 0, host = null }: DecomposeInput): string | null {
  const text = intent.trim();
  if (!text || !safeIds(project, workspace, areaId)) return null;
  const target = decomposeTarget(host);
  if (target === "none") return null;
  if (target === "cards" && host) return phasePrompt({ project, workspace, areaId, areaName, text, cards, host });
  return [
    "/opora-control-center",
    `Jsi rozkladač oblasti. Projekt ${project}, workspace ${workspace}, oblast id ${areaId}. Postupuj podle references/rozklad.md.`,
    ...dataBlock("Záměr", [
      `Název oblasti: ${oneLine(areaName)}`,
      `Záměr oblasti: ${quoted(text)}`,
      `Počet sektorů v oblasti: ${sectors}`,
    ]),
    "Aktuální název, záměr a sektory oblasti ber z `opora_read.py view --raw`; když se od kopie výše liší, nic nezapisuj a vrať blokaci.",
    "Před návrhem načti profil a pravidla projektu a porovnej záměr s účelem a akceptací existujících sektorů; navrhuj jen nepokrytou část: 1–7 sektorů, obvykle 2–5. Když stačí 0–1 sektor, nebo vstup nejde načíst, dávku nestav a vrať jeden souhrn; prázdný projekt, chybějící mapa kódu, prázdná pravidla ani prázdný cíl profilu blokace nejsou. Produktové volby, které záměr nenese, dej pod dávku do „Otázek pro člověka“, ne do akceptace.",
    `Dávka \`/api/canvas-plan\`: každý sektor s \`parent: "@${areaId}"\` (backend ho položí dovnitř rámečku oblasti) a jednou kartou [gate] s \`parent\` = ref sektoru; jiné karty nezakládej a existující sektory neměň.`,
    "Nejdřív `--dry-run`; ke schválení ukaž celou dávku (u každého sektoru název, účel, cíl, akceptaci a bránu). Souhlas platí jen pro přesně ten soubor a digest; ostře zapiš až po něm.",
  ].join("\n");
}

/** Fáze sektoru: karty do rámečku oblasti; cíl, akceptaci a bránu čte agent ze sektoru, ne z oblasti. */
function phasePrompt({ project, workspace, areaId, areaName, text, cards, host }: {
  project: string; workspace: string; areaId: string; areaName: string; text: string; cards: number; host: AreaHost;
}): string | null {
  if (!safeIds(host.id)) return null;
  return [
    "/opora-control-center",
    `Jsi rozkladač sektoru. Projekt ${project}, workspace ${workspace}, sektor id ${host.id}, fáze (oblast uvnitř sektoru) id ${areaId}. Postupuj podle references/rozklad.md, oddíly „Sektor → karty“ a „Fáze sektoru → karty“.`,
    ...dataBlock("Fáze", [
      `Název sektoru: ${oneLine(host.name)}`,
      `Název fáze: ${oneLine(areaName)}`,
      `Záměr fáze: ${quoted(text)}`,
      `Počet karet ve fázi: ${cards}`,
    ]),
    `Nejdřív ověř z \`opora_read.py view --raw\`, že oblast ${areaId} leží ve vrstvě sektoru ${host.id} (\`parentId\`) a že název sektoru, název fáze, záměr fáze a počet karet ve fázi sedí s kopií výše; když ne, nic nezapisuj a vrať blokaci. Ostatní podklady jsou aktuální stav, ne kopie.`,
    `Cíl, mimo rozsah, akceptaci, pravidla a bránu čti ze sektoru: \`node-brief --node ${host.id} --raw\`; karty sektoru (ve všech fázích) z \`view --raw\`. Sektor musí mít \`gateNodeId\` ukazující na existující kartu [gate] ve své vrstvě; chybí-li nebo je neplatná, je to blokace (novou [gate] nezakládáš).`,
    "Navrhuj jen tu část akceptace sektoru, kterou záměr fáze pokrývá a existující karty (ve fázi i jinde v sektoru) nepokrývají: 1–9 karet, obvykle 3–7. Když nic nechybí, nebo vstup nejde načíst, dávku nestav a vrať jeden souhrn.",
    `Dávka \`/api/canvas-plan\`: každá karta s \`parent: "@${areaId}"\` (backend ji položí dovnitř rámečku fáze ve vrstvě sektoru), předponou [task] / [research] / [prototype], purpose, spec {goal, non_goals, acceptance}, bloky s condition a porty, sourceRef, checks u karty s testy. Vazby zakládáš jen z nových karet: next / block mezi nimi, na existující karty a na kartu [gate] sektoru; vazby existujících karet neměníš. Když by napojení vyžadovalo změnit existující vazbu nebo kartu, dávku nestav a uveď to v souhrnu blokací. Kartu [gate], existující karty ani jiné fáze neměň; proces kartám pak určí router.`,
    "Nejdřív `--dry-run`; ke schválení ukaž celou dávku (u každé karty název, účel, cíl, akceptaci, bloky s porty a vazby). Souhlas platí jen pro přesně ten soubor a digest; ostře zapiš až po něm.",
  ].join("\n");
}
