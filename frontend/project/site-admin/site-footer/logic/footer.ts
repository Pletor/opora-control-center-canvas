// Patička webu `settings.footer` (backend `backend/project/site_admin/site_chrome.py`): sloupce odkazů, sociální
// sítě, právní řádek, rozvržení a odkaz „Nastavení cookies“, kterým návštěvník kdykoli změní souhlas (odvolat
// souhlas musí jít stejně snadno jako ho dát, EDPB 05/2020). Styl `.ds-footer` je v `components.css`.
import { HTTPS, readPart, type SiteLink } from "@/project/site-admin/site-fields/logic/settings-part";

export type FooterVariant = "columns" | "simple" | "centered";
export type Column = { title: string; links: SiteLink[] };
export type Social = { name: string; url: string };
export type Footer = { columns: Column[]; legal: string; social: Social[]; variant: FooterVariant; cookieLink: boolean };

export const EMPTY_FOOTER: Footer = { columns: [], legal: "", social: [], variant: "columns", cookieLink: true };
export const MAX_COLUMNS = 6;
export const MAX_LINKS = 12;
export const MAX_SOCIAL = 12;
export const NETWORKS: Record<string, string> = {
  facebook: "Facebook", instagram: "Instagram", linkedin: "LinkedIn", x: "X", youtube: "YouTube", tiktok: "TikTok",
  github: "GitHub", pinterest: "Pinterest", mastodon: "Mastodon", other: "Jiná síť",
};

export const readFooter = (settings: Record<string, unknown>): Footer => readPart(settings, "footer", EMPTY_FOOTER);

export const footerClass = (footer: Footer): string => `ds-footer ds-footer--${footer.variant}`;

export const socialProblem = (item: Social): string => HTTPS.test(item.url.trim()) ? "" : "Adresa profilu je https://…";

/** Právní řádek s rokem: `{rok}` se nahradí letošním rokem, prázdný řádek dá vzor. */
export const legalLine = (legal: string, year: number): string => (legal || "© {rok} Provozovatel webu, IČO …").replace(/\{rok\}/g, String(year));

/** Rada jako u serveru: patička s obsahem bez právního řádku. */
export const footerAdvice = (footer: Footer): string =>
  (footer.columns.length || footer.social.length) && !footer.legal.trim() ? "Chybí právní řádek (provozovatel, IČO, copyright)." : "";
