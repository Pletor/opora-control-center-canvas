import { isCount, isNullableText, isObject, isText } from "@/hub/oporahub-mirror/logic/hub-read";

// Registr lidských identit (docs/oporahub-review-identity.md). `marker` nese nonce: smí ho vidět jen člověk
// na obrazovce, nikdy agent (data-oh-*, JSON zrcadlo).
export type IdentityState = "claimed" | "verified" | "revoked";
export type Identity = {
  identityId: string; name: string; githubLogin: string; githubUserId: number | null; state: IdentityState;
  operator: boolean; claimedAt: string | null; verifiedAt: string | null; revokedAt: string | null;
  evidence: Record<string, unknown> | null; marker?: string;
};
export type PublicIdentity = Omit<Identity, "marker">;
const STATES: IdentityState[] = ["claimed", "verified", "revoked"];

function identity(value: unknown): value is Identity {
  return isObject(value) && isText(value.identityId, 200) && isText(value.name, 400) && isText(value.githubLogin, 200)
    && (value.githubUserId === null || value.githubUserId === undefined || isCount(value.githubUserId))
    && STATES.includes(value.state as IdentityState) && typeof value.operator === "boolean"
    && [value.claimedAt, value.verifiedAt, value.revokedAt].every(item => item === undefined || isNullableText(item))
    && (value.evidence === null || value.evidence === undefined || isObject(value.evidence))
    && (value.marker === undefined || isText(value.marker, 400));
}
const normalize = (value: Identity): Identity => ({ ...value, githubUserId: value.githubUserId ?? null, claimedAt: value.claimedAt ?? null,
  verifiedAt: value.verifiedAt ?? null, revokedAt: value.revokedAt ?? null, evidence: value.evidence ?? null });

export function parseIdentities(raw: unknown): Identity[] {
  if (!isObject(raw) || !Array.isArray(raw.items) || !raw.items.every(identity)) throw new Error("Registr identit má neplatný tvar.");
  return raw.items.map(normalize);
}
export function parseIdentity(raw: unknown): Identity {
  if (!identity(raw)) throw new Error("Identita má neplatný tvar.");
  return normalize(raw);
}

/** Co smí vidět agent: stejná fakta bez ověřovacího řádku (nonce). */
export function publicIdentities(items: Identity[]): PublicIdentity[] {
  return items.map(({ marker: _marker, ...rest }) => rest);
}

export const identitiesUrl = (project: string) => `/api/oporahub/review-identities?${new URLSearchParams({ project })}`;
export const identityActionUrl = (identityId: string, action: "verify" | "revoke") =>
  `/api/oporahub/review-identities/${encodeURIComponent(identityId)}/${action}`;
export const CLAIM_URL = "/api/oporahub/review-identities/claim";

export const stateView: Record<IdentityState, { glyph: string; label: string; tone: "ok" | "warn" | "gap" }> = {
  verified: { glyph: "✓", label: "ověřeno", tone: "ok" },
  claimed: { glyph: "◷", label: "čeká na ověření", tone: "warn" },
  revoked: { glyph: "◌", label: "zrušeno", tone: "gap" },
};

/** Odkaz na důkaz jen na github.com přes https; cokoli jiného se nezobrazí jako odkaz. */
export function evidenceUrl(item: Pick<Identity, "evidence">): string | null {
  const url = item.evidence?.url ?? item.evidence?.commentUrl;
  return typeof url === "string" && /^https:\/\/github\.com\/[^\s"'<>]+$/.test(url) ? url : null;
}

const ERRORS: Record<string, string> = {
  identity_proof_missing: "Komentář s přesným řádkem od nárokovaného účtu se nenašel. Vložte řádek jako samostatný řádek komentáře a zkuste to znovu.",
  human_required: "Tuto akci smí provést jen člověk v lidské session.",
  github_unavailable: "GitHub teď není dostupný. Zkuste to později.",
  review_conflict: "Požadavek je v rozporu se stavem registru (např. operátor už existuje nebo účet patří jiné identitě).",
  not_found: "Identita v tomto projektu neexistuje.",
  identity_required: "Chybí identita relace. Obnovte stránku.",
};
export function identityError(error: unknown): string {
  const value = error as { status?: number; body?: { code?: unknown; error?: unknown }; message?: string };
  const code = typeof value?.body?.code === "string" ? value.body.code : "";
  if (ERRORS[code]) return ERRORS[code];
  if (value?.status === 428) return ERRORS.identity_required;
  return value?.message || "Požadavek se nezdařil.";
}
