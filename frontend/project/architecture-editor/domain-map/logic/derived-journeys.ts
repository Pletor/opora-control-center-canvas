// Odvozené kroky cest zákazníka z backendu (`GET /api/project-architecture/journeys`, docs/architektura-pro-agenty.md §6).
// Čistá logika bez Reactu: adresa dotazu, obranné čtení odpovědi a věta pro řádek cesty. Kroky počítá jen backend.

/** Výsledek odvození jedné cesty: buď řada kroků (`line`), nebo důvod přerušení (`broken`). */
export type DerivedJourney = { applicationId: string; id: string; line?: string; broken?: string };

export function derivedJourneysUrl(project: string): string {
  return "/api/project-architecture/journeys?" + new URLSearchParams({ project });
}

const text = (value: unknown) => (typeof value === "string" && value ? value : undefined);

/** Položky bez id aplikace a cesty nebo bez `line` i `broken` zahodí; neznámý tvar odpovědi = žádné cesty. */
export function normalizeDerivedJourneys(raw: unknown): DerivedJourney[] {
  const items = raw && typeof raw === "object" ? (raw as { journeys?: unknown }).journeys : undefined;
  if (!Array.isArray(items)) return [];
  return items.flatMap((item): DerivedJourney[] => {
    if (!item || typeof item !== "object") return [];
    const { applicationId, id, line, broken } = item as Record<string, unknown>;
    const app = text(applicationId), journey = text(id), path = text(line), reason = text(broken);
    if (!app || !journey || (!path && !reason)) return [];
    return [{ applicationId: app, id: journey, ...(reason ? { broken: reason } : { line: path }) }];
  });
}

/** Cesty jedné domény podle id cesty (id je jedinečné jen v aplikaci). */
export function derivedForDomain(items: DerivedJourney[], domainId: string): Map<string, DerivedJourney> {
  return new Map(items.filter((item) => item.applicationId === domainId).map((item) => [item.id, item]));
}

/** Co ukázat u cesty: řada kroků, nebo „cesta je přerušená: důvod“; bez odvození nic. */
export function derivedJourneyText(derived: DerivedJourney | undefined): { text: string; broken: boolean } | null {
  if (!derived) return null;
  return derived.broken ? { text: "cesta je přerušená: " + derived.broken, broken: true } : { text: derived.line ?? "", broken: false };
}
