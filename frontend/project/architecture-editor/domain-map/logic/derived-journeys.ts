// Odvozené údaje cest zákazníka z backendu (`GET /api/project-architecture/journeys`, docs/architektura-pro-agenty.md §6).
// Čistá logika bez Reactu: adresa dotazu, obranné čtení odpovědi a co ukázat u kroku trychtýře. Vazby počítá jen backend.

/** Přechod mezi dvěma kroky: `realized` = mapa ho vazbami realizuje; `line` = realizace (nebo jen oba kroky). */
export type DerivedSegment = { from: string; to: string; line: string; realized: boolean };
/** Odvození jedné cesty: kroky, jejichž stránka chybí (`missing`), přechody a u rozbité cesty důvod (`broken`). */
export type DerivedJourney = { applicationId: string; id: string; missing: string[]; segments: DerivedSegment[]; broken?: string };

export function derivedJourneysUrl(project: string): string {
  return "/api/project-architecture/journeys?" + new URLSearchParams({ project });
}

const text = (value: unknown) => (typeof value === "string" && value ? value : undefined);
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const record = (value: unknown): Record<string, unknown> => (value && typeof value === "object" ? value as Record<string, unknown> : {});

function segment(raw: unknown): DerivedSegment[] {
  const { from, to, line, realized } = record(raw);
  const source = text(from), target = text(to);
  return source && target && typeof realized === "boolean" ? [{ from: source, to: target, line: text(line) ?? "", realized }] : [];
}

/** Položky bez id aplikace a cesty zahodí; neznámý tvar odpovědi = žádné cesty. */
export function normalizeDerivedJourneys(raw: unknown): DerivedJourney[] {
  return list(record(raw).journeys).flatMap((item): DerivedJourney[] => {
    const { applicationId, id, steps, segments, broken } = record(item);
    const app = text(applicationId), journey = text(id), reason = text(broken);
    if (!app || !journey) return [];
    const missing = list(steps).flatMap((step) => { const { id: stepId, missing: gone } = record(step); return gone === true && text(stepId) ? [stepId as string] : []; });
    return [{ applicationId: app, id: journey, missing, segments: list(segments).flatMap(segment), ...(reason ? { broken: reason } : {}) }];
  });
}

/** Cesty jedné domény podle id cesty (id je jedinečné jen v aplikaci). */
export function derivedForDomain(items: DerivedJourney[], domainId: string): Map<string, DerivedJourney> {
  return new Map(items.filter((item) => item.applicationId === domainId).map((item) => [item.id, item]));
}

/** Stav kroku podle odvození: chybí jeho stránka, nebo k němu z předchozího kroku nevede vazba; bez odvození nic. */
export function derivedStepState(derived: DerivedJourney | undefined, stepId: string): { missing: boolean; unrealized: string | null } {
  const into = derived?.segments.find((item) => item.to === stepId);
  return { missing: derived?.missing.includes(stepId) ?? false, unrealized: into && !into.realized ? into.line : null };
}
