// Tvar `GET /api/project-architecture/web-status` (docs/domeny-a-worktree.md §8, §9) a jeho slova.
// Chybějící DNS je u domén, které ještě nikdo nenasadil, normální stav: tón je neutrální, ne chyba.

export type WebState = "dns_missing" | "dns_no_web" | "unreachable" | "up" | "degraded" | "unchecked";
export type WebTone = "ok" | "warn" | "bad" | "neutral";
export type WebHost = {
  domainId: string; environment: string; host: string; state: WebState;
  httpStatus: number | null; health: string | null; latencyMs: number | null; checkedAt: string | null; detail: string;
};

export const WEB_STATE: Record<WebState, { label: string; icon: string; tone: WebTone }> = {
  up: { label: "běží", icon: "✓", tone: "ok" },
  degraded: { label: "degradováno", icon: "!", tone: "warn" },
  unreachable: { label: "nedostupné", icon: "✕", tone: "bad" },
  dns_missing: { label: "DNS neexistuje", icon: "∅", tone: "neutral" },
  dns_no_web: { label: "DNS bez webu", icon: "◌", tone: "neutral" },
  unchecked: { label: "neověřeno", icon: "?", tone: "neutral" },
};

const STATES = Object.keys(WEB_STATE) as WebState[];
const text = (value: unknown) => (typeof value === "string" ? value : "");
const num = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : null);

export function normalizeWebStatus(raw: unknown): WebHost[] {
  const hosts = raw && typeof raw === "object" && Array.isArray((raw as { hosts?: unknown }).hosts) ? (raw as { hosts: unknown[] }).hosts : [];
  return hosts.map((value) => {
    const item = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
    return {
      domainId: text(item.domainId), environment: text(item.environment), host: text(item.host),
      state: STATES.find((state) => state === item.state) ?? "unchecked",
      httpStatus: num(item.httpStatus), health: text(item.health) || null, latencyMs: num(item.latencyMs),
      checkedAt: text(item.checkedAt) || null, detail: text(item.detail),
    };
  }).filter((host) => host.host);
}

/**
 * Odpověď nahradí, co pokrývá: plná odpověď (`domainId = null`) celý seznam, odpověď jedné domény
 * všechny záznamy té domény. Host, který z architektury zmizel, tak v seznamu nezůstane viset.
 */
export function applyHosts(prev: WebHost[], next: WebHost[], domainId: string | null): WebHost[] {
  if (domainId === null) return next;
  return [...prev.filter((host) => host.domainId !== domainId), ...next.filter((host) => host.domainId === domainId)];
}

export function hostOf(hosts: WebHost[], domainId: string): WebHost | null {
  return hosts.find((host) => host.domainId === domainId) ?? null;
}

/** Ruční obnovení nejdřív 30 s po poslední kontrole hostu (docs/domeny-a-worktree.md §8). */
export const REFRESH_COOLDOWN_MS = 30_000;

/** Kolik celých sekund zbývá do dalšího ručního ověření; bez času kontroly hned. */
export function refreshWait(checkedAt: string | null | undefined, now: number): number {
  const moment = checkedAt ? parseIso(checkedAt) : NaN;
  if (Number.isNaN(moment)) return 0;
  return Math.min(REFRESH_COOLDOWN_MS / 1000, Math.max(0, Math.ceil((moment + REFRESH_COOLDOWN_MS - now) / 1000)));
}

/** `title` tlačítka „Ověřit znovu“: proč je zakázané, nebo co udělá. */
export function refreshTitle(wait: number): string {
  return wait > 0 ? `Další ověření za ${wait} s` : "Ověří host znovu; backend drží výsledek 60 s.";
}

/** Zastaralý údaj webu: čas poslední kontroly hostu (`checkedAt`), jen když poslední čtení selhalo. */
export function webStaleNote(host: WebHost | null, failed: boolean): string {
  if (!failed || !host?.checkedAt) return "";
  return `údaj z ${clockOf(host.checkedAt)}, nepodařilo se obnovit`;
}

/** Text žetonu: „běží · 120 ms“, „DNS neexistuje“. */
export function badgeText(host: WebHost | null): string {
  const state = host?.state ?? "unchecked";
  const latency = host?.latencyMs != null && (state === "up" || state === "degraded") ? ` · ${Math.round(host.latencyMs)} ms` : "";
  return WEB_STATE[state].label + latency;
}

/** `title` žetonu: host, HTTP kód, health, podrobnost a čas kontroly. */
export function badgeTitle(host: WebHost | null): string {
  if (!host) return "Web ještě nebyl ověřen.";
  const parts = [host.host, WEB_STATE[host.state].label];
  if (host.httpStatus != null) parts.push(`HTTP ${host.httpStatus}`);
  if (host.health) parts.push(`health ${host.health}`);
  if (host.detail) parts.push(host.detail);
  if (host.checkedAt) parts.push(`ověřeno ${clockOf(host.checkedAt)}`);
  return parts.join(" · ");
}

/** ISO čas → „12:03“ v místním čase; neplatný → původní text. */
export function clockOf(iso: string): string {
  const moment = new Date(parseIso(iso));
  if (Number.isNaN(moment.getTime())) return iso;
  return `${String(moment.getHours()).padStart(2, "0")}:${String(moment.getMinutes()).padStart(2, "0")}`;
}

/** ISO bez zóny backend posílá v UTC. */
export function parseIso(iso: string): number {
  return Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
}
