import { applyHosts, hostOf, webStaleNote, type WebHost } from "./web-status";

// Stav webu po doménách: jeden seznam hostů a ke každému rozsahu dotazu (celý projekt = „*“, nebo
// jedna doména) vlastní načítání, chyba a čas. Přehled se ptá na celý projekt, detail jen na svou
// doménu; chyba jedné domény tak nezčervená ostatní karty a načítání jedné nezablokuje jinou.

export const ALL_DOMAINS = "*";
export type WebScopeMeta = { loading: boolean; error: string; failures: number; updatedAt: number | null; at: number };
export type WebLive = { hosts: WebHost[]; scopes: Record<string, WebScopeMeta>; loaded: boolean };
/** Co o webu jedné domény vykreslí dílek. */
export type WebView = { host: WebHost | null; stale: string; loading: boolean; error: string };

const blank: WebScopeMeta = { loading: false, error: "", failures: 0, updatedAt: null, at: 0 };

export const emptyWeb = (): WebLive => ({ hosts: [], scopes: {}, loaded: false });
export const webScope = (domainId: string | null) => domainId ?? ALL_DOMAINS;

const withScope = (state: WebLive, scope: string, patch: Partial<WebScopeMeta>): WebLive =>
  ({ ...state, scopes: { ...state.scopes, [scope]: { ...blank, ...state.scopes[scope], ...patch } } });

export const webLoading = (state: WebLive, scope: string): WebLive => withScope(state, scope, { loading: true });

/** Dotaz skončil, ale jeho výsledek se zahodil (předběhl ho novější): jen zhasne „načítám“. */
export const webSettled = (state: WebLive, scope: string): WebLive => withScope(state, scope, { loading: false });

/** Plná odpověď platí pro všechny domény, proto smaže i jejich staré chyby. */
export function webLoaded(state: WebLive, scope: string, hosts: WebHost[], now: number): WebLive {
  const fresh = { error: "", failures: 0, updatedAt: now, at: now };
  const next = { ...state, hosts: applyHosts(state.hosts, hosts, scope === ALL_DOMAINS ? null : scope), loaded: true };
  if (scope !== ALL_DOMAINS) return withScope(next, scope, { ...fresh, loading: false });
  const scopes = Object.fromEntries(Object.entries(state.scopes).map(([key, meta]) => [key, { ...meta, ...fresh }]));
  return { ...next, scopes: { ...scopes, [ALL_DOMAINS]: { ...blank, ...state.scopes[ALL_DOMAINS], ...fresh, loading: false } } };
}

/** Chyba nechá hosty; zapíše se jen k rozsahu, kterého se dotaz týkal. */
export function webFailed(state: WebLive, scope: string, error: string, now: number): WebLive {
  return withScope(state, scope, { loading: false, error, failures: (state.scopes[scope]?.failures ?? 0) + 1, at: now });
}

/** Web jedné domény: platí novější z událostí domény a celého projektu; zastaralost podle `checkedAt`. */
export function webView(state: WebLive, domainId: string): WebView {
  const own = state.scopes[domainId];
  const all = state.scopes[ALL_DOMAINS];
  const latest = [own, all].filter((meta): meta is WebScopeMeta => !!meta).sort((a, b) => b.at - a.at)[0];
  const host = hostOf(state.hosts, domainId);
  const error = latest?.error ?? "";
  return { host, error, loading: !!(own?.loading || all?.loading), stale: webStaleNote(host, !!error) };
}

/** Text chyby celého projektu, dokud se web nenačetl ani jednou (přehled domén ji musí říct). */
export function webLoadNotice(state: WebLive): string {
  const error = state.scopes[ALL_DOMAINS]?.error;
  return !state.loaded && error ? `Stav webu se nepodařilo načíst: ${error}` : "";
}
