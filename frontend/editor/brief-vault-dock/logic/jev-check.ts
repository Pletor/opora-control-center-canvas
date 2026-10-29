// Povolení poradní kontroly bran přes Jev (docs/schranka-neurony.md §7, §9 bod 10): stav pro aktivního
// poskytovatele a věta, co přesně tím odejde ven. Kontrolu volají agenti (`POST /api/brief-vault/gate-check`);
// bez povolení člověka pro projekt a poskytovatele server nepošle nic. Bez Reactu.
export type JevProvider = "typesafe" | "celeris";
/** `GET /api/brain/jev`. */
export type JevStatus = { configured: boolean; provider: JevProvider; keys: Record<JevProvider, boolean> };
/** `GET /api/brain/jev/gate-check?project` → povolení po poskytovatelích. */
export type JevPermission = { project: string; allowed: Record<JevProvider, boolean> };

export const PROVIDER_LABELS: Record<JevProvider, string> = { typesafe: "TypeSafe", celeris: "Celeris" };

export type JevState = "unknown" | "not-configured" | "not-allowed" | "allowed";

/** Stav kontroly pro aktivního poskytovatele: bez klíče, bez povolení, nebo povoleno. */
export function jevState(status: JevStatus | undefined, permission: JevPermission | undefined): JevState {
  if (!status || !permission) return "unknown";
  if (!status.configured) return "not-configured";
  return permission.allowed[status.provider] ? "allowed" : "not-allowed";
}

/** Co člověk povolením pouští ven (věta u přepínače). */
export const consentText = (provider: JevProvider): string =>
  `Povolením souhlasíš, že při každé kontrole brány, o kterou agent požádá, odejde poskytovateli ${PROVIDER_LABELS[provider]} ` +
  "mimo tento počítač název fragmentu, jeho text (nejvýš 4000 znaků), název brány a payload. Nic dalšího; kontrola je jen poradní a bránu nezapne.";
