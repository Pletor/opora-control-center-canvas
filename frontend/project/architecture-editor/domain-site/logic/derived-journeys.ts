// Odvozené údaje cest zákazníka z backendu (`GET /api/project-architecture/journeys`, docs/architektura-pro-agenty.md §6).
// Čistá logika bez Reactu: adresa dotazu, obranné čtení odpovědi a co ukázat u kroku trychtýře. Vazby počítá jen backend.

/** Přechod mezi dvěma kroky: `realized` = mapa ho vazbami realizuje; `line` = realizace (nebo jen oba kroky). */
export type DerivedSegment = { from: string; to: string; line: string; realized: boolean };
/** Poslední doklad přehrání cesty (docs/brana-cesty.md §4): `stale` = mapa se od běhu změnila, `failed` = počet
 * neúspěšných přechodů, `firstFailure` první z nich. */
export type JourneyLastRun = {
  at: string; passed: boolean; stale: boolean; command: string; failed: number;
  firstFailure?: { from: string; to: string; reason?: string };
};
/** Cesta se právě přehrává (docs/brana-cesty.md §3a, stav jen v paměti serveru): `at` = poslední heartbeat runneru,
 * `segment` = přechod, který se přehrává (bez `ok`) nebo právě skončil; null = běh začal, přechod ještě nehlásil. */
export type JourneyRunning = { runId: string; at: string; segment: { from: string; to: string; ok?: boolean } | null };
/** Odvození jedné cesty: kroky, jejichž stránka chybí (`missing`), přechody, u rozbité cesty důvod (`broken`), poslední
 * doklad přehrání (`lastRun`, jen když cesta doklad má) a běžící přehrání (`running`, jen když právě běží). */
export type DerivedJourney = { applicationId: string; id: string; missing: string[]; segments: DerivedSegment[]; broken?: string; lastRun?: JourneyLastRun; running?: JourneyRunning };

/** Interval čtení cest: 15 s v klidu, 3 s když některá cesta právě běží (tečky mají sledovat aktuální přechod). */
export const RUNS_POLL_MS = 15_000;
export const RUNNING_POLL_MS = 3_000;
export const runsPollMs = (journeys: readonly DerivedJourney[] | null) => (journeys?.some((journey) => journey.running) ? RUNNING_POLL_MS : RUNS_POLL_MS);

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

/** `lastRun` jen v úplném tvaru (`at`, `passed`, `stale`); chybějící čísla a texty se čtou tolerantně. */
function lastRun(raw: unknown): JourneyLastRun | undefined {
  const { at, passed, stale, command, failed, firstFailure } = record(raw);
  const when = text(at);
  if (!when || typeof passed !== "boolean" || typeof stale !== "boolean") return undefined;
  const first = record(firstFailure), from = text(first.from), to = text(first.to), reason = text(first.reason);
  return { at: when, passed, stale, command: text(command) ?? "", failed: typeof failed === "number" && failed >= 0 ? failed : 0,
    ...(from && to ? { firstFailure: { from, to, ...(reason ? { reason } : {}) } } : {}) };
}

/** `running` jen s `runId` a `at`; přechod jen s `from` i `to`, `ok` jen jako bool. */
function running(raw: unknown): JourneyRunning | undefined {
  const { runId, at, segment: hop } = record(raw);
  const id = text(runId), when = text(at);
  if (!id || !when) return undefined;
  const { from, to, ok } = record(hop), source = text(from), target = text(to);
  return { runId: id, at: when, segment: source && target ? { from: source, to: target, ...(typeof ok === "boolean" ? { ok } : {}) } : null };
}

/** Položky bez id aplikace a cesty zahodí; neznámý tvar odpovědi = žádné cesty. */
export function normalizeDerivedJourneys(raw: unknown): DerivedJourney[] {
  return list(record(raw).journeys).flatMap((item): DerivedJourney[] => {
    const { applicationId, id, steps, segments, broken, lastRun: run, running: live } = record(item);
    const app = text(applicationId), journey = text(id), reason = text(broken), verified = lastRun(run), playing = running(live);
    if (!app || !journey) return [];
    const missing = list(steps).flatMap((step) => { const { id: stepId, missing: gone } = record(step); return gone === true && text(stepId) ? [stepId as string] : []; });
    return [{ applicationId: app, id: journey, missing, segments: list(segments).flatMap(segment), ...(reason ? { broken: reason } : {}),
      ...(verified ? { lastRun: verified } : {}), ...(playing ? { running: playing } : {}) }];
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
