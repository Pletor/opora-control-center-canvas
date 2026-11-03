// Panel Komponenty na přehledu domén: knihovna univerzálních komponent (docs/navrhy/2026-11-04-sprava-webu-design-system.md
// §0 M1 bod 5). Karty jsou statický seznam; katalogové karty čtou předlohy z Knihovny, Skills a Tools z registru Brainu
// (`GET /api/brain-registry/artifacts`), Harness z přehledu čtení dokumentace (`GET /api/oporahub/harness-documentation`).
// Vše jen ke čtení. Bez Reactu, test vedle.
import { CATALOG_ITEMS, type CatalogCategory, type CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";

export type BrainKind = "skill" | "tool";
export type ShelfSource = { kind: "catalog"; categories: CatalogCategory[] } | { kind: "brain"; artifact: BrainKind } | { kind: "harness" };
export type ShelfEntry = { id: string; label: string; source: ShelfSource };

const catalog = (...categories: CatalogCategory[]): ShelfSource => ({ kind: "catalog", categories });

/** Pořadí podle `image6.png`: základ webu a aplikace, pak doplňky, nakonec knihovny Brainu. */
export const COMPONENT_SHELF: ShelfEntry[] = [
  { id: "database", label: "Databáze", source: catalog("database") },
  { id: "backend", label: "Backend", source: catalog("backend") },
  { id: "devops", label: "DevOps", source: catalog("devops") },
  { id: "cache", label: "Cache", source: catalog("cache") },
  { id: "docker", label: "Docker", source: catalog("docker") },
  { id: "functions", label: "Funkce a metody", source: catalog("functions") },
  { id: "infrastructure", label: "Infrastruktura", source: catalog("cloud") },
  { id: "security", label: "Security", source: catalog("security") },
  { id: "monitoring", label: "Monitoring", source: catalog("monitoring") },
  { id: "tests", label: "Testy", source: catalog("tests") },
  { id: "tenancy", label: "Autentizace a tenancy", source: catalog("tenancy") },
  { id: "events", label: "Fronta a události", source: catalog("events") },
  { id: "storage", label: "Úložiště souborů", source: catalog("storage") },
  { id: "notifications", label: "Notifikace a push", source: catalog("notifications") },
  { id: "payments", label: "Platby", source: catalog("payments") },
  { id: "analytics", label: "Analytika", source: catalog("analytics") },
  { id: "search", label: "Vyhledávání", source: catalog("search") },
  { id: "config", label: "Konfigurace a feature flags", source: catalog("config") },
  { id: "skills", label: "Skills", source: { kind: "brain", artifact: "skill" } },
  { id: "tools", label: "Tools", source: { kind: "brain", artifact: "tool" } },
  { id: "harness", label: "Harness", source: { kind: "harness" } },
];

/** ID karty pro agenta (čip ID). */
export const shelfId = (entry: ShelfEntry) => "opora:library:" + entry.id;

/** Předlohy katalogové karty v pořadí katalogu; ostatní karty předlohy nemají. */
export function shelfItems(entry: ShelfEntry, items: CatalogItem[] = CATALOG_ITEMS): CatalogItem[] {
  const source = entry.source;
  return source.kind === "catalog" ? items.filter((item) => source.categories.includes(item.category)) : [];
}

export type BrainArtifact = { id: string; kind: string; name: string; plugin: string; active: { version: string; status: string } | null };
export type HarnessRead = { resource: string; library: string; fetchedAt: string; durationMs: number };
export type HarnessOverview = { scanned: number; invalid: number; conflicts: number; limited: boolean; reads: HarnessRead[] };
/** Stav zdroje: `null` = ještě se načítá, `error` = věta, proč se nepodařilo. */
export type Loaded<T> = { data: T | null; error: string };
export type ShelfData = { brain: Loaded<BrainArtifact[]>; harness: Loaded<HarnessOverview> };

const text = (value: unknown) => (typeof value === "string" ? value : "");
const record = (value: unknown): Record<string, unknown> => (value && typeof value === "object" ? value as Record<string, unknown> : {});

/** Odpověď registru Brainu na seznam artefaktů; nepoužitelné řádky se vynechají. */
export function parseBrainArtifacts(value: unknown): BrainArtifact[] {
  const rows = record(value).artifacts;
  return (Array.isArray(rows) ? rows : []).map(record).filter((row) => text(row.id)).map((row) => {
    const active = row.active ? record(row.active) : null;
    return { id: text(row.id), kind: text(row.kind), name: text(row.name), plugin: text(row.plugin),
      active: active && text(active.version) ? { version: text(active.version), status: text(active.status) } : null };
  });
}

/** Odpověď `harness.documentation-reads/1` na přehled: počty a ohlášená čtení dokumentace. */
export function parseHarness(value: unknown): HarnessOverview {
  const body = record(value);
  const count = (key: string) => (typeof body[key] === "number" ? body[key] as number : 0);
  const reads = (Array.isArray(body.observations) ? body.observations : []).map((entry) => record(record(entry).observation)).map((item) => ({
    resource: text(record(item.resource).id), library: text(item.library), fetchedAt: text(item.fetchedAt),
    durationMs: typeof item.durationMs === "number" ? item.durationMs : 0,
  }));
  return { scanned: count("scannedReceipts"), invalid: count("invalidReceipts"), conflicts: count("conflictingReads"), limited: body.limited === true, reads };
}

export const brainOf = (artifacts: BrainArtifact[], kind: BrainKind) => artifacts.filter((artifact) => artifact.kind === kind);
/** Krátká verze pro čtení (prvních 12 znaků SHA), celá zůstává v `title`. */
export const shortVersion = (version: string) => version.slice(0, 12);

/** Co karta ukáže pod názvem: počet předloh, artefaktů s aktivní verzí nebo čtení dokumentace; `null` = ještě se načítá. */
export function shelfCount(entry: ShelfEntry, data: ShelfData): string | null {
  const source = entry.source;
  if (source.kind === "catalog") return plural(shelfItems(entry).length, "předloha", "předlohy", "předloh");
  if (source.kind === "brain") {
    if (data.brain.error) return "nenačteno";
    if (!data.brain.data) return null;
    const own = brainOf(data.brain.data, source.artifact);
    return `${own.length} · ${own.filter((artifact) => artifact.active).length} aktivních`;
  }
  if (data.harness.error) return "nenačteno";
  return data.harness.data ? plural(data.harness.data.reads.length, "čtení", "čtení", "čtení") : null;
}

function plural(count: number, one: string, few: string, many: string): string {
  return `${count} ${count === 1 ? one : count >= 2 && count <= 4 ? few : many}`;
}
