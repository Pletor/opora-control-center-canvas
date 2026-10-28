// Zadání pro agenta-rozkladače stránky (docs/architektura-pro-agenty.md §5.2): stránka → sekce → komponenty → kroky.
// Čistá funkce bez Reactu a bez modelu; tlačítko „Kopírovat zadání rozkladu“ jen zkopíruje výsledek. Do instrukčních
// vět jdou jen ověřené identifikátory, vše volné (cíl, sekce, cesty, díry, knihovna) v jednom datovém bloku.
// Tvar dávky drží `references/canvas-plan.md`, postup `references/rozklad.md` oddíl „Stránka → komponenty“.
import { dataBlock, oneLine, safeIds } from "@/shared/agent-prompt/logic/agent-prompt";
import { CATALOG_ITEMS, type CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";
import type { Graph } from "@/shared/types/logic/types";
import type { MapCheck } from "../../../domain-map/map-check/logic/map-check";
import { pageDecomposeFacts, type DecomposeFacts } from "./page-decompose-model";

export type PageDecomposeInput = {
  project: string; workspace: string; graph: Graph; pageId: string;
  /** Kontrola mapy projektu (`useMapCheck`); `null` = nenačtená, agent si díry přečte sám. */
  check: MapCheck | null;
  catalog?: CatalogItem[];
};

/** Proč zadání nejde sestavit (česky), nebo `null`. Bez cíle stránky rozklad nemá z čeho stavět: to je díra člověka. */
export function pageDecomposeProblem(facts: DecomposeFacts | null): string | null {
  if (!facts) return "Prvek není stránka.";
  if (!facts.goal) return "Stránka nemá cíl; doplňte ho ve formuláři stránky.";
  return null;
}

const list = (values: readonly string[] | undefined) => (values?.length ? values.join(", ") : "");
const part = (label: string, value: string | undefined) => (value ? `; ${label} ${value}` : "");

function journeyLines(facts: DecomposeFacts): string[] {
  if (!facts.journeys.length) return ["(stránka neleží na žádné cestě zákazníka)"];
  return facts.journeys.flatMap((slice) => [
    `- Cesta ${oneLine(slice.journeyName)}, krok ${slice.step}/${slice.stepCount} „${oneLine(slice.role)}“` +
      part("aktér", slice.actor && oneLine(slice.actor)) + part("A →", slice.pointA && oneLine(slice.pointA)) + part("B:", slice.pointB && oneLine(slice.pointB)),
    ...(slice.shift ? [`  posun: ${oneLine(slice.shift)}`] : []),
    ...(slice.objection ? [`  námitka: ${oneLine(slice.objection)}`] : []),
    slice.from ? `  přichází z: ${oneLine(slice.from.role)} (${oneLine(slice.from.pageLabel)})${slice.from.signal ? " – " + oneLine(slice.from.signal.text) : ""}`
      : `  vstup: ${slice.entry ?? "první krok cesty"}`,
    ...slice.next.map((next) => `  další krok: ${oneLine(next.role)} (${oneLine(next.pageLabel)}${next.pageId ? ", id " + next.pageId : ""}); via na této stránce: ${next.signal ? oneLine(next.signal.text) : "neurčeno"}`
      + (next.signal?.missingSection ? ` [sekce ${next.signal.missingSection} na stránce chybí]` : "")),
  ]);
}

function componentLines(facts: DecomposeFacts): string[] {
  if (!facts.components.length) return ["(stránka zatím nemá komponenty)"];
  return facts.components.map((item) => `- ${item.id} „${oneLine(item.name)}“; sekce ${item.section ?? "neurčena"}` + part("tech", item.tech && oneLine(item.tech))
    + part("stavy", item.states && oneLine(list(item.states)))
    + part("ven", list(item.out.map((edge) => `${edge.carries} → ${oneLine(edge.to)}`)))
    + part("dovnitř", list(item.in.map((edge) => `${edge.carries} ← ${oneLine(edge.from)}`))));
}

function holeLines(facts: DecomposeFacts): string[] {
  if (facts.holes === null) return ["(kontrola mapy není načtená; přečti GET /api/project-architecture/map-check)"];
  if (!facts.holes.length) return ["(kontrola mapy na stránce nic nehlásí)"];
  return facts.holes.map((hole) => `- ${hole.rule}: ${oneLine(hole.message)}`);
}

/** Položky knihovny s kontextem pro agenta (porty nebo díry `fill`), jedna na řádek. */
export function libraryLines(catalog: CatalogItem[]): string[] {
  return catalog.filter((item) => item.ports?.length || item.fill?.length).map((item) => `- ${item.id} „${oneLine(item.label)}“`
    + part("tech", item.tech) + part("stavy", list(item.states))
    + part("porty", list(item.ports?.map((port) => `${port.direction} ${port.id}:${port.carries}`)))
    + part("fetch", list([...(item.fetch?.files ?? []), ...(item.fetch?.docs ?? [])])) + part("fill", list(item.fill)));
}

const ITEM_SHAPE = '{"ref": "formular", "kind": "node", "parent": "@PAGE", "name": "[task] …", "purpose": "…", '
  + '"card": {"layer": "frontend", "section": "<id sekce>", "tech": "…", "states": ["…", "chyba"]}, '
  + '"spec": {"goal": "…", "non_goals": "…", "acceptance": "- …\\n- …"}}';
const EDGE_SHAPE = '{"from": "formular", "to": "@<id stránky nebo komponenty>", "port": "next", "carries": "navigation|data|command|event"}';

/** Hotové zadání rozkladu stránky, nebo `null` (neplatný identifikátor, uzel není stránka, stránka bez cíle). */
export function pageDecomposePrompt({ project, workspace, graph, pageId, check, catalog = CATALOG_ITEMS }: PageDecomposeInput): string | null {
  if (!safeIds(project, workspace, pageId)) return null;
  const facts = pageDecomposeFacts(graph, pageId, check);
  if (pageDecomposeProblem(facts) || !facts) return null;
  const sections = facts.sections.length
    ? facts.sections.map((section) => `- ${section.id} · ${section.role} · ${oneLine(section.intent) || "(bez záměru)"}${section.moves ? " · posouvá: " + oneLine(section.moves) : ""}`)
    : ["(stránka nemá sekce; navrhni je nejdřív v `site.sections` stránky)"];
  const write = `opora_write.py /api/canvas-plan --project ${project} --workspace ${workspace} --json-file "<draftsDir>/plan-${pageId}-<čas>.json"`;
  return [
    "/opora-control-center",
    `Jsi rozkladač stránky. Projekt ${project}, workspace ${workspace}, stránka id ${pageId}. Postupuj podle references/rozklad.md, oddíl „Stránka → komponenty“; tvar dávky references/canvas-plan.md, kroky references/planner.md.`,
    ...dataBlock("Podklady stránky", [
      `Stránka: ${oneLine(facts.name)} (${oneLine(facts.path) || "bez cesty"})`,
      `Cíl: ${oneLine(facts.goal ?? "")}`,
      `Působení: ${facts.feel ? oneLine(facts.feel) : "(neurčeno)"}`,
      "Sekce (id · role · záměr · posouvá):", ...sections,
      "Cesty zákazníka přes stránku:", ...journeyLines(facts),
      "Existující komponenty:", ...componentLines(facts),
      "Díry mapy stránky:", ...holeLines(facts),
      "Knihovna (id · tech · stavy · porty · fetch · fill):", ...libraryLines(catalog),
    ]),
    `1. Ověř kopii: \`opora_read.py view --raw\` (stránka ${pageId}, její sekce, komponenty a digest) a \`opora_read.py node-brief --node ${pageId} --raw\` (architecture: cesty, holes). Když se cíl, sekce nebo komponenty liší od kopie, nic nezapisuj a vrať blokaci.`,
    "2. Pokrytí: každá sekce bez komponenty dostane aspoň jednu; každý další krok cesty potřebuje komponentu v sekci jeho `via` s prvkem jeho textu a vazbu `next` s `carries: navigation` (klik) nebo `command` (odeslání) směrem ke stránce dalšího kroku; díry mapy stránky zacel. Existující komponenty neměň (chybějící `card.section`, `tech`, `states` jen přes `extend`). Když nic nechybí, vrať souhrn, ne dávku.",
    "3. Knihovna: komponenta, která odpovídá položce knihovny, převezme její `tech`, `states` a porty jako vazby s `carries`; soubory z `fetch` si přečti a pole z `fill` vyplň. Nic dalšího nevymýšlej; produktové volby, které podklady nenesou, dej do „Otázek pro člověka“.",
    `4. Dávka \`/api/canvas-plan\`: položka ${ITEM_SHAPE.replace("@PAGE", "@" + pageId)}; vazba ${EDGE_SHAPE}. \`card.section\` jen z existujících sekcí stránky, \`tech\` a \`states\` jen doložené, odesílající komponenta má stav „chyba“.`,
    `5. Nejdřív \`${write} --dry-run\`; ke schválení ukaž celou dávku (u každé komponenty název, účel, sekce, cíl, akceptace, stavy, vazby s carries) s cestou k souboru a sha256. Ostře týž soubor bez \`--dry-run\` až po souhlasu.`,
    "6. Kroky: po zápisu navrhni každé nové komponentě `spec.steps` (tvar a kontrolní seznam v planner.md) návrhem změny zadání `opora_write.py /api/oporahub/changesets` nad `GET /api/oporahub/changesets/context`; přijímá člověk. Karta, kterou kontext ještě nezná, kroky nedostane: uveď je v souhrnu.",
  ].join("\n");
}

/** Rodič předá dílkům funkci nad id stránky; karta i hlavička se tak nemusí dívat do grafu ani kontroly mapy. */
export type PageDecompose = (pageId: string) => { prompt: string | null; problem: string | null };

/** Co dostane tlačítko: hotové zadání, nebo česky důvod, proč nejde sestavit (tlačítko je pak vypnuté s tímto popiskem). */
export function pageDecomposeOffer(input: PageDecomposeInput): { prompt: string | null; problem: string | null } {
  const problem = !safeIds(input.project, input.workspace, input.pageId)
    ? "Identifikátor projektu, workspace nebo stránky obsahuje nepovolené znaky."
    : pageDecomposeProblem(pageDecomposeFacts(input.graph, input.pageId, input.check));
  return problem ? { prompt: null, problem } : { prompt: pageDecomposePrompt(input), problem: null };
}
