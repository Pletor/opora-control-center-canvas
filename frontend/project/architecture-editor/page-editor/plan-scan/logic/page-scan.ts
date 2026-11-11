// Sken webu přes REA (docs/navrhy/2026-11-10-platno-2.md, Verze 3 „Sken přes REA“ a Verze 6): spuštění, dotaz na stav,
// obnova nepřevzatého návrhu, Zahodit a tolerantní převod odpovědi na návrh layoutu, designu a logiky s tokem dat.
// Server výstup validuje; klient ho přesto čte opatrně, aby chybějící nebo cizí pole nikdy neshodila plátno.
// Bez Reactu (síť jen v exportovaných async funkcích), test vedle.
import { api, ApiError, type ElementKind, type PageSection, type PageSectionRole } from "@/shared/types/logic/types";
import { SECTION_ROLE_LABELS, MAX_PAGE_SECTIONS } from "../../../domain-site/logic/page-site";
import { LOGIC_GROUPS } from "../../element-palette/logic/logic-groups";
import { layoutSections, type LayoutSection } from "../../layout-canvas/logic/layout-grid";
import { settleLayout } from "../../layout-canvas/logic/settle-layout";

/** Jak prvek funguje (Verze 6): každý seznam nejvýš 8 položek po 160 znacích; `dataTo` = kam data odcházejí. */
export type ScanFlow = { inputs: string[]; steps: string[]; outputs: string[]; conditions: string[]; dataTo: string[] };
export type ScanLogic = { ref: string; kind: ElementKind; name: string; purpose: string; section: string | null; flow?: ScanFlow };
/** Box návrhu: `selector` (CSS selektor prvku na webu pro výřez) jen čte náhled, do layoutu se nezapisuje. */
export type ScanSection = LayoutSection & { selector?: string };
/** Snímky skenu: celá stránka a výřezy boxů (jméno souboru ve složce skenu, čte `captureUrl`). */
export type ScanCaptures = { page: string | null; sections: Record<string, string> };
export type ScanProposal = { sections: ScanSection[]; logic: ScanLogic[]; screenshot: string | null;
  /** Tokeny webu ve tvaru `design.tokens` Správy webu (server je prohnal `normalize_tokens`). */
  design: Record<string, unknown> | null; captures: ScanCaptures | null; notes: string[] };
export type ScanState =
  | { state: "running" }
  | { state: "done"; proposal: ScanProposal; cost: number | null }
  | { state: "failed"; error: string };
type Scope = { project: string; workspace: string };

const GRAPH_ID = /^[A-Za-z0-9_-]{1,80}$/;
const CAPTURE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/;
const LOGIC_MAX = 100;
const FLOW_ITEMS = 8, FLOW_TEXT = 160;
export const SECTION_INTENT_MAX = 600, SECTION_LOOK_MAX = 300;
const KINDS = new Set<string>(LOGIC_GROUPS.flatMap((group) => group.kinds.map((item) => item.kind)));
const record = (value: unknown): Record<string, unknown> => (value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {});
const text = (value: unknown, max: number) => (typeof value === "string" ? value.trim().slice(0, max) : "");
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

/** Sekce návrhu: platné a unikátní id, známá role (jinak Vlastní), název (jinak popisek role), box v mezích mřížky,
 * rodič jen na sekci návrhu bez cyklu; vždy `status: "proposed"`. Nejvýš 40 sekcí, usazené bez překryvu (náhled = převzetí). */
export function normalizeProposalSections(raw: unknown): ScanSection[] {
  const seen = new Set<string>();
  const sections: (PageSection & { selector?: string })[] = [];
  for (const item of list(raw).map(record)) {
    const id = text(item.id, 80);
    if (!GRAPH_ID.test(id) || seen.has(id) || sections.length >= MAX_PAGE_SECTIONS) continue;
    seen.add(id);
    const role = (typeof item.role === "string" && item.role in SECTION_ROLE_LABELS ? item.role : "custom") as PageSectionRole;
    const box = record(item.box);
    const numeric = ["x", "y", "w", "h"].every((key) => typeof box[key] === "number");
    const look = text(item.look, SECTION_LOOK_MAX), selector = text(item.selector, 300);
    sections.push({ id, role, name: text(item.name, 60) || SECTION_ROLE_LABELS[role], intent: text(item.intent, SECTION_INTENT_MAX), status: "proposed",
      ...(numeric ? { box: { x: box.x as number, y: box.y as number, w: box.w as number, h: box.h as number } } : {}),
      ...(typeof item.parent === "string" ? { parent: item.parent } : {}), ...(look ? { look } : {}), ...(selector ? { selector } : {}) });
  }
  return settleLayout(layoutSections(sections) as ScanSection[]);
}

/** Sekce k zápisu layoutu: bez `selector` (backend ho v `site.sections` nezná), usazené bez překryvu. */
export const layoutOfProposal = (sections: readonly ScanSection[]): LayoutSection[] => settleLayout(sections.map(({ selector: _selector, ...section }) => section));

/** Tok prvku: jen textové položky, nejvýš 8 v seznamu po 160 znacích; bez jediné položky = žádný tok. */
export function normalizeFlow(raw: unknown): ScanFlow | undefined {
  const value = record(raw);
  const items = (key: string) => list(value[key]).map((item) => text(item, FLOW_TEXT)).filter(Boolean).slice(0, FLOW_ITEMS);
  const flow = { inputs: items("inputs"), steps: items("steps"), outputs: items("outputs"), conditions: items("conditions"), dataTo: items("dataTo") };
  return Object.values(flow).some((entries) => entries.length) ? flow : undefined;
}

/** Snímky: jen bezpečná jména souborů, výřezy jen pro sekce návrhu; nic = `null`. */
export function normalizeCaptures(raw: unknown, sectionIds: ReadonlySet<string>): ScanCaptures | null {
  const value = record(raw);
  const page = typeof value.page === "string" && CAPTURE_NAME.test(value.page) ? value.page : null;
  const sections = Object.fromEntries(Object.entries(record(value.sections))
    .filter((entry): entry is [string, string] => sectionIds.has(entry[0]) && typeof entry[1] === "string" && CAPTURE_NAME.test(entry[1])));
  return page || Object.keys(sections).length ? { page, sections } : null;
}

/** Prvky logiky návrhu: jen druhy z palety logiky, název (jinak druh), box jen ze sekcí návrhu (jinak celá stránka). */
export function normalizeProposalLogic(raw: unknown, sectionIds: ReadonlySet<string>): ScanLogic[] {
  return list(raw).map(record).filter((item) => typeof item.kind === "string" && KINDS.has(item.kind)).slice(0, LOGIC_MAX).map((item, index) => {
    const kind = item.kind as ElementKind;
    const section = typeof item.section === "string" && sectionIds.has(item.section) ? item.section : null;
    const label = LOGIC_GROUPS.flatMap((group) => group.kinds).find((entry) => entry.kind === kind)!.label;
    const flow = normalizeFlow(item.flow);
    return { ref: text(item.ref, 80) || `logic-${index}`, kind, name: text(item.name, 160) || label, purpose: text(item.purpose, 500), section, ...(flow ? { flow } : {}) };
  });
}

/** Odpověď `GET /api/page-plan/scan/{scanId}`: neznámý stav nebo hotovo bez boxů = chyba s větou, nikdy výjimka. */
export function normalizeScan(raw: unknown): ScanState {
  const value = record(raw);
  if (value.state === "running") return { state: "running" };
  if (value.state === "failed") return { state: "failed", error: text(value.error, 500) || "Sken selhal bez udaného důvodu." };
  if (value.state !== "done") return { state: "failed", error: "Server vrátil neznámý stav skenu." };
  const proposal = record(value.proposal);
  const sections = normalizeProposalSections(proposal.sections);
  if (!sections.length) return { state: "failed", error: "Sken nevrátil žádný box layoutu." };
  const ids = new Set(sections.map((section) => section.id));
  const logic = normalizeProposalLogic(proposal.logic, ids);
  const screenshot = typeof proposal.screenshot === "string" && proposal.screenshot ? proposal.screenshot : null;
  const design = proposal.design && typeof proposal.design === "object" && !Array.isArray(proposal.design) ? proposal.design as Record<string, unknown> : null;
  const notes = list(proposal.notes).map((note) => text(note, 300)).filter(Boolean).slice(0, 20);
  return { state: "done", proposal: { sections, logic, screenshot, design, captures: normalizeCaptures(proposal.captures, ids), notes },
    cost: typeof value.cost === "number" ? value.cost : null };
}

/** `POST /api/page-plan/scan` → id běžícího skenu. */
export async function startScan(scope: Scope, pageId: string, url: string, note: string): Promise<string> {
  const value = record(await api<unknown>("/api/page-plan/scan", { ...scope, pageId, url: url.trim(), ...(note.trim() ? { note: note.trim() } : {}) }));
  const scanId = text(value.scanId, 200);
  if (!scanId) throw new Error("Server sken nespustil (chybí scanId).");
  return scanId;
}

/** Převzetí layoutu návrhu: `POST /api/page-plan` se `scanId` (server boxům zapíše `source: "scan"`) nad otiskem
 * plánu z `GET /api/page-plan`; souběžná změna layoutu = 409 od serveru. */
export async function adoptScanLayout(scope: Scope, pageId: string, sections: PageSection[], scanId: string): Promise<void> {
  const plan = record(await api<unknown>("/api/page-plan?" + new URLSearchParams({ ...scope, pageId })));
  if (typeof plan.digest !== "string") throw new Error("Plán stránky se nepodařilo načíst (chybí digest).");
  await api("/api/page-plan", { ...scope, pageId, expectedDigest: plan.digest, sections, scanId });
}

const scanPath = (scanId: string) => `/api/page-plan/scan/${encodeURIComponent(scanId)}`;

export async function readScan(scope: Scope, scanId: string): Promise<ScanState> {
  return normalizeScan(await api<unknown>(scanPath(scanId) + "?" + new URLSearchParams(scope)));
}

/** Poslední hotový a nepřevzatý sken stránky (`GET /api/page-plan/scan/latest`); 404 = žádný. */
export async function readLatestScan(scope: Scope, pageId: string): Promise<{ scanId: string; state: ScanState } | null> {
  try {
    const raw = record(await api<unknown>("/api/page-plan/scan/latest?" + new URLSearchParams({ ...scope, pageId })));
    const scanId = text(raw.scanId, 200);
    return scanId ? { scanId, state: normalizeScan(raw) } : null;
  } catch (cause) { if (cause instanceof ApiError && cause.status === 404) return null; throw cause; }
}

/** Zahodit návrh (`POST /api/page-plan/scan/{scanId}/discard`, jen člověk): obnova ho už neukáže. */
export async function discardScan(scope: Scope, scanId: string): Promise<void> {
  await api(scanPath(scanId) + "/discard", scope);
}

/** Adresa snímku skenu (celá stránka nebo výřez boxu); server vydá jen jména ze záznamu skenu. */
export const captureUrl = (scope: Scope, scanId: string, name: string) =>
  `${scanPath(scanId)}/capture/${encodeURIComponent(name)}?` + new URLSearchParams(scope);

/** Stáhne PNG snímku skenu (pro nahrání jako inspirace boxu). */
export async function fetchCapture(scope: Scope, scanId: string, name: string): Promise<Blob> {
  const response = await fetch(captureUrl(scope, scanId, name), { cache: "no-store" });
  if (!response.ok) throw new Error(`Snímek ${name} není dostupný (HTTP ${response.status}).`);
  return response.blob();
}
