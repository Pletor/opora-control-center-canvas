// Cookie lišta a kontakt správce `settings.gdpr` (backend `backend/project/site_admin/site_settings.py`).
// Pravidla (ePrivacy čl. 5 odst. 3, EDPB Guidelines 05/2020, EDPB Cookie Banner Taskforce 2023, ÚOOÚ):
// nezbytné cookies souhlas nepotřebují a jsou vždy zapnuté; ostatní kategorie jsou předem vypnuté (nic předem
// zaškrtnutého), „Odmítnout vše“ je na první vrstvě stejně výrazné jako „Přijmout vše“, zavření lišty není souhlas
// a odvolat souhlas jde kdykoli stejně snadno (plovoucí tlačítko, odkaz v patičce).
import { readPart } from "@/project/site-admin/site-fields/logic/settings-part";

export type Category = "necessary" | "preferences" | "analytics" | "marketing";
export type Position = "bottom" | "top" | "bottom-left" | "bottom-right" | "center";
export type CategoryInfo = { label: string; description: string };
export type CookieBar = {
  enabled: boolean; position: Position; title: string; text: string; categories: Category[];
  categoryInfo: Partial<Record<Category, CategoryInfo>>; acceptLabel: string; rejectLabel: string; settingsLabel: string; saveLabel: string;
  policyPageId: string; policyUrl: string; consentDays: number; reopen: boolean; version: number;
};
export type Contact = { controller: string; email: string; dpoEmail: string; address: string };
export type Gdpr = { cookieBar: CookieBar; contact: Contact };
export type Consent = Record<Category, boolean>;

export const CATEGORIES: Category[] = ["necessary", "preferences", "analytics", "marketing"];
export const DEFAULT_INFO: Record<Category, CategoryInfo> = {
  necessary: { label: "Nezbytné", description: "Bez nich web nefunguje (přihlášení, košík, uložení této volby). Souhlas nepotřebují." },
  preferences: { label: "Předvolby", description: "Pamatují si jazyk, region nebo vzhled webu." },
  analytics: { label: "Analytické", description: "Měří návštěvnost, abychom web zlepšovali. Údaje jsou souhrnné." },
  marketing: { label: "Marketingové", description: "Personalizovaná reklama a kódy partnerů (affiliate)." },
};
export const DEFAULT_TEXT = "Používáme cookies. Nezbytné potřebuje web k fungování, ostatní jen s tvým souhlasem. Volbu můžeš kdykoli změnit.";

export const EMPTY_GDPR: Gdpr = {
  cookieBar: {
    enabled: false, position: "bottom", title: "", text: "", categories: ["necessary"], categoryInfo: {},
    acceptLabel: "Přijmout vše", rejectLabel: "Odmítnout vše", settingsLabel: "Nastavení", saveLabel: "Uložit výběr",
    policyPageId: "", policyUrl: "", consentDays: 180, reopen: true, version: 1,
  },
  contact: { controller: "", email: "", dpoEmail: "", address: "" },
};
export const CONSENT_ADVISED = 395;  // 13 měsíců

export const readGdpr = (settings: Record<string, unknown>): Gdpr => readPart(settings, "gdpr", EMPTY_GDPR);

/** Kategorie zapnutá na webu nebo vypnutá; nezbytné zůstanou vždy a pořadí je pevné. */
export function withCategory(bar: CookieBar, category: Category, on: boolean): CookieBar {
  const categories = CATEGORIES.filter((item) => item === "necessary" || (item === category ? on : bar.categories.includes(item)));
  const { [category]: _gone, ...rest } = bar.categoryInfo;
  return { ...bar, categories, categoryInfo: on ? bar.categoryInfo : rest };
}

export const info = (bar: CookieBar, category: Category): CategoryInfo => ({
  label: bar.categoryInfo[category]?.label || DEFAULT_INFO[category].label,
  description: bar.categoryInfo[category]?.description || DEFAULT_INFO[category].description,
});

/** Výchozí volba návštěvníka: jen nezbytné (výchozí odmítnutí), nic předem zaškrtnutého. */
export const initialConsent = (): Consent => ({ necessary: true, preferences: false, analytics: false, marketing: false });
export const acceptAll = (bar: CookieBar): Consent => Object.fromEntries(CATEGORIES.map((item) => [item, bar.categories.includes(item)])) as Consent;
export const toggleConsent = (consent: Consent, category: Category): Consent => category === "necessary" ? consent : { ...consent, [category]: !consent[category] };

export const barClass = (bar: CookieBar): string => `ds-cookie-bar ds-cookie-bar--${bar.position}`;

/** Rady stejné jako poznámky serveru. */
export function gdprAdvice(gdpr: Gdpr): string[] {
  const bar = gdpr.cookieBar;
  if (!bar.enabled) return [];
  const out: string[] = [];
  if (!bar.policyPageId && !bar.policyUrl) out.push("Chybí odkaz na zásady cookies (stránka nebo URL).");
  if (bar.categories.length === 1) out.push("Jen nezbytné cookies souhlas nepotřebují, lišta pak není nutná; stačí informace v zásadách.");
  if (bar.consentDays > CONSENT_ADVISED) out.push("Úřady doporučují ptát se znovu nejpozději po 13 měsících.");
  if (!gdpr.contact.email) out.push("Chybí e-mail správce pro dotazy a odvolání souhlasu.");
  return out;
}
