// Panel Komponenty na přehledu domén: složky knihovny pláten toku (`library-shelf.ts`, kontrakt
// docs/navrhy/2026-11-04-knihovna-platna-toku.md §4) a za nimi tři knihovny Brainu, které zůstávají odkazem do Brainu:
// Skills a Tools z registru Brainu (`GET /api/brain-registry/artifacts`), Harness z přehledu čtení dokumentace
// (`GET /api/oporahub/harness-documentation`). Brain jen ke čtení. Bez Reactu, test vedle.

export type BrainKind = "skill" | "tool";
export type ShelfSource = { kind: "brain"; artifact: BrainKind } | { kind: "harness" };
export type ShelfEntry = { id: string; label: string; source: ShelfSource };

/** Knihovny Brainu na konci panelu (pořadí podle `image6.png`). */
export const BRAIN_SHELF: ShelfEntry[] = [
  { id: "skills", label: "Skills", source: { kind: "brain", artifact: "skill" } },
  { id: "tools", label: "Tools", source: { kind: "brain", artifact: "tool" } },
  { id: "harness", label: "Harness", source: { kind: "harness" } },
];

/** ID karty pro agenta (čip ID). */
export const shelfId = (entry: ShelfEntry) => "opora:library:" + entry.id;

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

/** Co karta ukáže pod názvem: počet artefaktů s aktivní verzí nebo čtení dokumentace; `null` = ještě se načítá. */
export function shelfCount(entry: ShelfEntry, data: ShelfData): string | null {
  const source = entry.source;
  if (source.kind === "brain") {
    if (data.brain.error) return "nenačteno";
    if (!data.brain.data) return null;
    const own = brainOf(data.brain.data, source.artifact);
    return `${own.length} · ${own.filter((artifact) => artifact.active).length} aktivních`;
  }
  if (data.harness.error) return "nenačteno";
  return data.harness.data ? plural(data.harness.data.reads.length, "čtení", "čtení", "čtení") : null;
}

export function plural(count: number, one: string, few: string, many: string): string {
  return `${count} ${count === 1 ? one : count >= 2 && count <= 4 ? few : many}`;
}
