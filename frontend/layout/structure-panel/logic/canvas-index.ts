// Shody z jednotného indexu plátna (`GET /api/canvas-index`, docs/kontext-karet-a-index.md §5) pro
// sekci Struktura. Bez Reactu a bez sítě: dostane hotovou odpověď a vrátí, která id karet strom
// ukáže a které vazby půjdou do skupiny „Vazby“. Hledá backend; tady se nic nehledá znovu.

/** Záznam karty v indexu (`kind` sector | node | area). */
export type CardIndexEntry = {
  id: string;
  kind: "sector" | "node" | "area";
  name: string;
  /** Typ workflow z předpony názvu (`[task] …`), jinak null. */
  type: string | null;
  /** Vrstva karty (`frontend` | `backend` | `database` | `library`), jinak null. */
  layer: string | null;
  status: string | null;
  due: string | null;
  path: string[];
  address: string;
  parentId: string | null;
  sectorId: string | null;
  purpose: string;
  sourcePath: string | null;
  text: string;
};

/** Záznam vazby v indexu. */
export type EdgeIndexEntry = {
  id: string;
  kind: "edge";
  port: string;
  from: string;
  to: string;
  fromName: string;
  toName: string;
  fromAddress: string;
  toAddress: string;
  summary: string;
  handoff: string;
  sentAt: string;
  due: string;
  text: string;
};

export type CanvasIndexEntry = CardIndexEntry | EdgeIndexEntry;
export type CanvasIndexResponse = { entries: CanvasIndexEntry[]; total: number };

/** Řádek skupiny „Vazby“: odkud kam a krátce, co se předává. */
export type EdgeMatch = { id: string; from: string; fromName: string; toName: string; handoff: string };

/** Shody pro strom: id karet (bez vazeb) a vazby zvlášť. */
export type IndexMatches = { ids: ReadonlySet<string>; edges: EdgeMatch[] };

export const HANDOFF_PREVIEW = 80;

/** Předání zkráceně na jeden řádek: zalomení pryč, nejvýš `max` znaků se třemi tečkami. */
export function shortText(text: string, max = HANDOFF_PREVIEW): string {
  const flat = (text ?? "").replace(/\s+/g, " ").trim();
  return flat.length > max ? flat.slice(0, max - 1).trimEnd() + "…" : flat;
}

/** Odpověď indexu na shody; neznámý tvar (starý backend, chyba) vrací `null` → panel spadne na lokální filtr. */
export function indexMatches(response: unknown): IndexMatches | null {
  if (!response || typeof response !== "object" || !Array.isArray((response as CanvasIndexResponse).entries)) return null;
  const ids = new Set<string>();
  const edges: EdgeMatch[] = [];
  for (const entry of (response as CanvasIndexResponse).entries) {
    if (!entry || typeof entry !== "object" || typeof entry.id !== "string") continue;
    if (entry.kind === "edge")
      edges.push({ id: entry.id, from: entry.from, fromName: entry.fromName || entry.from, toName: entry.toName || entry.to, handoff: shortText(entry.handoff || "") });
    else ids.add(entry.id);
  }
  return { ids, edges };
}

/** Strom potřebuje všechny shody, ne jen první stránku: graf má nejvýš 2000 uzlů, tolik je i maximum indexu. */
export const INDEX_LIMIT = 2000;

/** Adresa dotazu na index; `q` se posílá oříznutý, prázdný dotaz index nevolá vůbec. */
export const canvasIndexUrl = (project: string, workspace: string, query: string): string =>
  "/api/canvas-index?" + new URLSearchParams({ project, workspace, q: query.trim(), limit: String(INDEX_LIMIT) }).toString();
