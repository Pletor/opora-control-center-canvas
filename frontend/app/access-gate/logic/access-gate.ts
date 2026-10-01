/**
 * Rozhodnutí brány vzdáleného přístupu — čistá logika bez Reactu a bez sítě.
 *
 * Aplikace běží doma; ven ji pouští tunel. Backend v takovém případě říká
 * `GET /api/access/status` → `{remote, authenticated, host}`. Brána se ukáže jen tehdy,
 * když jsme skutečně venku a ještě nemáme token. Na loopbacku se neukáže nikdy.
 */
export type AccessStatus = { remote: boolean; authenticated: boolean; host: string };

/** Událost okna, kterou pošle `api()` při HTTP 401: token vypršel nebo nikdy nebyl. */
export const ACCESS_REQUIRED_EVENT = "opora:access-required";
/** Stejná dolní hranice jako na backendu (`MIN_TOKEN_LENGTH` v remote_access.py). */
export const MIN_TOKEN_LENGTH = 24;
/** Když se na stav nedá zeptat (starší backend, 404), bereme běh jako domácí. */
export const LOCAL_STATUS: AccessStatus = { remote: false, authenticated: true, host: "" };

/** Tolerantní čtení odpovědi: cokoli nečekaného znamená domácí běh, ne zamčenou aplikaci. */
export function statusFrom(value: unknown): AccessStatus {
  if (!value || typeof value !== "object") return LOCAL_STATUS;
  const row = value as Partial<AccessStatus>;
  if (typeof row.remote !== "boolean") return LOCAL_STATUS;
  return {
    remote: row.remote,
    authenticated: row.authenticated === true,
    host: typeof row.host === "string" ? row.host : "",
  };
}

/** Brána se ukáže jen venku a jen bez tokenu; dokud stav neznáme, nic se nerozhoduje. */
export const needsGate = (status: AccessStatus | null): boolean =>
  status !== null && status.remote && !status.authenticated;

/** Po 401 platí, že jsme venku a odhlášení — i kdyby předchozí stav tvrdil opak. */
export const lockedOut = (status: AccessStatus | null): AccessStatus => ({
  remote: true,
  authenticated: false,
  host: status?.host ?? "",
});

/** Odeslat jde jen token, který má šanci projít; prázdné pole nikam neposíláme. */
export const tokenIsUsable = (value: string): boolean => value.trim().length >= MIN_TOKEN_LENGTH;

/** Co se ukáže pod polem, když token nestačí; jinak nic. */
export function tokenHint(value: string): string {
  if (value.length === 0) return "";
  return tokenIsUsable(value) ? "" : `Token má nejméně ${MIN_TOKEN_LENGTH} znaků.`;
}
