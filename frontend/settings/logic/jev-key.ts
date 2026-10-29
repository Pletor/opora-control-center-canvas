/**
 * Klíč poskytovatele Jev v Nastavení → Jev (docs/brain-heart-channel.md §5). Bez Reactu a bez sítě.
 *
 * Stav se čte z `GET /api/brain/jev` → `{provider, configured, keys}`; server o klíči
 * vrací jen booleany, nikdy jeho hodnotu. Uložení a smazání jde přes `POST /api/brain/jev/key
 * {key: text | null, provider}`. Klíč platí pro celou aplikaci a čte se při každé zprávě, takže
 * změna platí bez restartu.
 */
import { PROVIDER_LABELS, type JevProvider, type JevStatus } from "@/editor/brief-vault-dock/logic/jev-check";

/** Stejná horní hranice jako na backendu (`MAX_TYPESAFE_KEY` v memory_service.py). */
export const MAX_JEV_KEY = 512;
const PROVIDERS = Object.keys(PROVIDER_LABELS) as JevProvider[];

/** Odpověď `GET /api/brain/jev`; cizí tvar = neznámý stav (null), ne „klíč chybí“. */
export function parseJevStatus(value: unknown): JevStatus | null {
  if (!value || typeof value !== "object") return null;
  const { configured, provider, keys } = value as { configured?: unknown; provider?: unknown; keys?: unknown };
  if (typeof configured !== "boolean" || !PROVIDERS.includes(provider as JevProvider)) return null;
  const flags = (keys && typeof keys === "object" ? keys : {}) as Record<string, unknown>;
  const parsed = Object.fromEntries(PROVIDERS.map((name) => [name, flags[name] === true])) as Record<JevProvider, boolean>;
  // Starší backend posílal jen `configured`; platí pro aktivního poskytovatele.
  parsed[provider as JevProvider] ||= configured;
  return { configured, provider: provider as JevProvider, keys: parsed };
}

/** Odeslat jde jen klíč, který backend přijme: neprázdný, bez mezer a řídicích znaků, do 512 znaků. */
export function jevKeyHint(draft: string): string {
  const key = draft.trim();
  if (!key) return "";
  if (key.length > MAX_JEV_KEY) return `Klíč má nejvýš ${MAX_JEV_KEY} znaků.`;
  if ([...key].some((char) => char.charCodeAt(0) < 33)) return "Klíč nesmí obsahovat mezery.";
  return "";
}

export const jevKeyIsUsable = (draft: string): boolean => draft.trim() !== "" && jevKeyHint(draft) === "";

/** Tělo POST; `null` klíč smaže. Poskytovatel se posílá vždy, ať se nesmaže jiný klíč, než člověk vidí. */
export const jevKeyPayload = (key: string | null, provider: JevProvider) =>
  ({ key: key === null ? null : key.trim(), provider });

export type JevKeyRow = { provider: JevProvider; label: string; active: boolean; configured: boolean; state: string };

/** Řádky pro každého poskytovatele: aktivní první, stav jen slovy „nastavený / nenastavený“. */
export function jevKeyRows(status: JevStatus): JevKeyRow[] {
  return [...PROVIDERS]
    .sort((a, b) => Number(b === status.provider) - Number(a === status.provider))
    .map((provider) => ({
      provider,
      label: PROVIDER_LABELS[provider],
      active: provider === status.provider,
      configured: status.keys[provider],
      state: status.keys[provider] ? "Klíč je nastavený" : "Klíč není nastavený",
    }));
}
