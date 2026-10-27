// Kontrola mapy z backendu (`GET /api/project-architecture/map-check`, docs/architektura-pro-agenty.md §5) pro mapu domény.
// Čistá logika bez Reactu: adresa dotazu, obranné čtení odpovědi, český popisek a rada pravidla, výběr nálezů jedné domény
// seskupený po pravidlech a kam vede klik na nález. Díry počítá jen backend; tady se nic neodhaduje.
import type { CanvasNode, Graph } from "@/shared/types/logic/types";

/** Pořadí pravidel jako `RULES` v `backend/project/architecture/map_check.py`. */
export const MAP_CHECK_RULES = ["journey.broken", "journey.unrealized", "journey.via-unknown", "journey.unverified", "page.no-goal", "section.unrealized", "section.unknown",
  "command.no-receiver", "state.no-error", "edge.carries-unset"] as const;
export type MapCheckRule = typeof MAP_CHECK_RULES[number];
export type MapCheckFinding = { rule: MapCheckRule; nodeId?: string; edgeId?: string; journeyId?: string; message: string };
export type MapCheck = { findings: MapCheckFinding[] };
/** Kam vede klik: stránka, komponenta (a její nejbližší stránka), cesta zákazníka, hrana (a stránka i uzel jejího zdroje). */
export type MapCheckTarget = { kind: "page"; id: string } | { kind: "journey"; id: string } | { kind: "node"; id: string; pageId: string }
  | { kind: "edge"; id: string; pageId: string; sourceId: string };
/** `place` = čitelné místo nálezu (název stránky či komponenty, cesty, nebo „zdroj → cíl“ u vazby); prázdné, když ho graf nezná. */
export type MapCheckItem = { finding: MapCheckFinding; target: MapCheckTarget | null; place: string };
export type MapCheckGroup = { rule: MapCheckRule; label: string; advice: string; items: MapCheckItem[] };

export const MAP_CHECK_TEXT: Record<MapCheckRule, { label: string; advice: string }> = {
  "journey.broken": { label: "Cesta ztratila stránku", advice: "Opravte krok cesty, nebo stránku vraťte." },
  "journey.unrealized": { label: "Přechod cesty nemá vazbu", advice: "Mezi stránkami chybí navigace, příkaz, data nebo sekce. Práce pro agenty." },
  "journey.via-unknown": { label: "Signál přechodu míří na neznámou sekci", advice: "V kroku cesty vyberte sekci, kterou předchozí stránka má." },
  "journey.unverified": { label: "Cesta není ověřená", advice: "Přehrajte cestu harnessem (plán: journey-plan) a odevzdejte doklad." },
  "page.no-goal": { label: "Stránka nemá cíl", advice: "Doplňte cíl stránky ve formuláři stránky." },
  "section.unrealized": { label: "Sekce nemá komponentu", advice: "Přiřaďte sekci aspoň jednu komponentu stránky." },
  "section.unknown": { label: "Karta odkazuje na neznámou sekci", advice: "Vyberte kartě sekci, kterou stránka má, nebo odkaz zrušte." },
  "command.no-receiver": { label: "Příkaz nikam nevede", advice: "Napojte vazbu příkazu na komponentu, která ho přijme." },
  "state.no-error": { label: "Odesílání bez stavu chyby", advice: "Přidejte komponentě stav „chyba“." },
  "edge.carries-unset": { label: "Vazba neříká, co nese", advice: "Nastavte vazbě, co nese (Detail prvku → Vazby)." },
};

export function mapCheckUrl(project: string): string {
  return "/api/project-architecture/map-check?" + new URLSearchParams({ project });
}

const text = (value: unknown) => (typeof value === "string" && value ? value : undefined);
const record = (value: unknown): Record<string, unknown> => (value && typeof value === "object" ? value as Record<string, unknown> : {});
const isRule = (value: unknown): value is MapCheckRule => (MAP_CHECK_RULES as readonly unknown[]).includes(value);

/** Nález s neznámým pravidlem nebo bez zprávy zahodí; neznámý tvar odpovědi = žádné nálezy. Nikdy nehodí výjimku. */
export function normalizeMapCheck(raw: unknown): MapCheck {
  const items = record(raw).findings;
  return { findings: (Array.isArray(items) ? items : []).flatMap((item): MapCheckFinding[] => {
    const { rule, nodeId, edgeId, journeyId, message } = record(item);
    const note = text(message), node = text(nodeId), edge = text(edgeId), journey = text(journeyId);
    if (!isRule(rule) || !note) return [];
    return [{ rule, ...(node ? { nodeId: node } : {}), ...(edge ? { edgeId: edge } : {}), ...(journey ? { journeyId: journey } : {}), message: note }];
  }) };
}

/** Uzel sám a jeho předci po `parentId`, odspodu; cyklus ani chybějící uzel nehodí výjimku. */
function lineage(byId: Map<string, CanvasNode>, id: string): CanvasNode[] {
  const chain: CanvasNode[] = [];
  for (let node = byId.get(id); node && !chain.includes(node); node = node.parentId ? byId.get(node.parentId) : undefined) chain.push(node);
  return chain;
}

/** Kam vede klik na nález v grafu `graph`; null = místo v grafu není (nebo komponenta neleží pod stránkou). */
export function mapCheckTarget(finding: MapCheckFinding, graph: Graph): MapCheckTarget | null {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const pageOf = (id: string) => lineage(byId, id).find((node) => node.site?.kind === "page")?.id;
  if (finding.nodeId) {
    const pageId = pageOf(finding.nodeId);
    if (!pageId) return null;
    return pageId === finding.nodeId ? { kind: "page", id: pageId } : { kind: "node", id: finding.nodeId, pageId };
  }
  if (finding.edgeId) {
    const edge = graph.edges.find((item) => item.id === finding.edgeId);
    const pageId = edge && pageOf(edge.source);
    return edge && pageId ? { kind: "edge", id: edge.id, pageId, sourceId: edge.source } : null;
  }
  return finding.journeyId ? { kind: "journey", id: finding.journeyId } : null;
}

/** Patří nález k doméně? Uzel a hrana (podle zdroje) leží pod doménou, cesta je v `site.journeys` domény. */
function inDomain(finding: MapCheckFinding, graph: Graph, byId: Map<string, CanvasNode>, domain: CanvasNode): boolean {
  if (finding.journeyId) return domain.site?.kind === "application" && (domain.site.journeys ?? []).some((journey) => journey.id === finding.journeyId);
  const nodeId = finding.nodeId ?? graph.edges.find((edge) => edge.id === finding.edgeId)?.source;
  return !!nodeId && lineage(byId, nodeId).some((node) => node.id === domain.id);
}

function nameOf(byId: Map<string, CanvasNode>, id: string): string {
  return byId.get(id)?.name.trim() || id;
}

/** Čitelné místo nálezu, aby se stejné zprávy (např. tři stránky bez cíle) daly rozlišit. */
export function mapCheckPlace(finding: MapCheckFinding, graph: Graph, domain: CanvasNode): string {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  if (finding.nodeId) return byId.has(finding.nodeId) ? nameOf(byId, finding.nodeId) : "";
  if (finding.edgeId) {
    const edge = graph.edges.find((item) => item.id === finding.edgeId);
    return edge ? `${nameOf(byId, edge.source)} → ${nameOf(byId, edge.target)}` : "";
  }
  const journeys = domain.site?.kind === "application" ? domain.site.journeys ?? [] : [];
  return journeys.find((journey) => journey.id === finding.journeyId)?.name.trim() || finding.journeyId || "";
}

/** Nálezy jedné domény seskupené po pravidlech v pořadí `MAP_CHECK_RULES`; prázdné skupiny vynechá. */
export function mapCheckGroups(check: MapCheck, graph: Graph, domain: CanvasNode): MapCheckGroup[] {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const mine = check.findings.filter((finding) => inDomain(finding, graph, byId, domain));
  return MAP_CHECK_RULES.flatMap((rule): MapCheckGroup[] => {
    const items = mine.filter((finding) => finding.rule === rule).map((finding) => ({ finding, target: mapCheckTarget(finding, graph), place: mapCheckPlace(finding, graph, domain) }));
    return items.length ? [{ rule, ...MAP_CHECK_TEXT[rule], items }] : [];
  });
}
