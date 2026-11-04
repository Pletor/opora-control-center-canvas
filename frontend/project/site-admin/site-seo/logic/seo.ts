// SEO webu `settings.seo` (backend `backend/project/site_admin/site_settings.py`): šablona titulku, popis, jazyk,
// robots, canonical, sitemap, Open Graph / Twitter a JSON-LD. Pravidla podle Google Search Central a Open Graph:
// výsledek vyhledávání ukáže zhruba 60 znaků titulku a 160 znaků popisu, delší text se ořízne.
import { readPart } from "@/project/site-admin/site-fields/logic/settings-part";

export type Robots = { index: boolean; follow: boolean; noarchive: boolean; nosnippet: boolean; maxImagePreview: string; maxSnippet: number };
export type Seo = {
  titleTemplate: string; siteName: string; description: string; locale: string; canonicalHost: string;
  ogImage: string; ogType: string; twitterCard: string; twitterSite: string; robots: Robots; sitemap: boolean; structuredData: string;
};

export const EMPTY_SEO: Seo = {
  titleTemplate: "%s", siteName: "", description: "", locale: "cs_CZ", canonicalHost: "", ogImage: "", ogType: "website",
  twitterCard: "summary_large_image", twitterSite: "",
  robots: { index: true, follow: true, noarchive: false, nosnippet: false, maxImagePreview: "large", maxSnippet: -1 },
  sitemap: true, structuredData: "",
};
export const TITLE_SHOWN = 60;
export const DESCRIPTION_SHOWN = 160;

export const readSeo = (settings: Record<string, unknown>): Seo => readPart(settings, "seo", EMPTY_SEO);

/** Titulek stránky podle šablony (`%s · Web`); šablona bez `%s` vrátí jen titulek. */
export const pageTitle = (template: string, title: string): string => template.includes("%s") ? template.replace("%s", title) : title;

/** Text, jak ho ořízne výsledek vyhledávání: nejvýš `limit` znaků, na konci výpustka. */
export const clip = (text: string, limit: number): string => text.length > limit ? text.slice(0, limit - 1).trimEnd() + "…" : text;

export const templateProblem = (template: string): string =>
  !template.trim() || template.split("%s").length === 2 ? "" : "Šablona obsahuje právě jednou %s (místo pro titulek stránky).";

const HOST = /^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/;
export const hostProblem = (host: string): string => !host.trim() || HOST.test(host.trim()) ? "" : "Host bez https:// a lomítek (www.example.cz).";

/** Obsah `<meta name="robots">` jako ho vypíše dělník. */
export function robotsContent(robots: Robots): string {
  return [robots.index ? "index" : "noindex", robots.follow ? "follow" : "nofollow",
    ...(robots.noarchive ? ["noarchive"] : []), ...(robots.nosnippet ? ["nosnippet"] : []),
    `max-image-preview:${robots.maxImagePreview}`, `max-snippet:${robots.maxSnippet}`].join(", ");
}

/** Chyba JSON-LD jako u serveru (platný JSON, objekt nebo pole objektů, bez `</`); prázdný text = v pořádku. */
export function structuredDataProblem(text: string): string {
  if (!text.trim()) return "";
  let data: unknown;
  try { data = JSON.parse(text); } catch (error) { return "JSON-LD není platný JSON: " + (error instanceof Error ? error.message : String(error)); }
  const objects = Array.isArray(data) ? data.length > 0 && data.every((item) => item && typeof item === "object" && !Array.isArray(item)) : !!data && typeof data === "object";
  if (!objects) return "JSON-LD je objekt nebo pole objektů.";
  return text.includes("</") ? "JSON-LD nesmí obsahovat </ (ukončil by značku script)." : "";
}

/** Vzor JSON-LD z toho, co už je vyplněné: WebSite a Organization (schema.org). */
export function structuredDataSample(seo: Seo, logo: string): string {
  const url = seo.canonicalHost ? `https://${seo.canonicalHost}/` : "https://www.example.cz/";
  const name = seo.siteName || "Název webu";
  return JSON.stringify({ "@context": "https://schema.org", "@graph": [
    { "@type": "WebSite", name, url, inLanguage: seo.locale.replace("_", "-") },
    { "@type": "Organization", name, url, ...(logo ? { logo } : {}) },
  ] }, null, 2);
}

/** Adresa ve výsledku vyhledávání: `host › cesta`. */
export const searchCrumb = (host: string, path: string): string =>
  [host || "www.example.cz", ...path.split("/").filter(Boolean)].join(" › ");
