// Části Nastavení webu (`settings.seo`, `email`, `header`, …), jak je normalizuje server
// (`backend/project/site_admin/site_settings.py`, `site_chrome.py`): vždy celý tvar s výchozími hodnotami.
// Frontend proto čte část proti vlastnímu výchozímu tvaru (starý nebo neúplný dokument nic nerozbije) a posílá ji
// celou zpátky. Odkaz menu a patičky míří buď na stránku mapy domény (`pageId`), nebo na URL.
import { siteAdminUrls } from "@/project/site-admin/logic/site-admin-api";

export type SiteLink = { label: string; pageId: string; url: string };
export const EMPTY_LINK: SiteLink = { label: "", pageId: "", url: "" };

type Plain = Record<string, unknown>;
const isPlain = (value: unknown): value is Plain => !!value && typeof value === "object" && !Array.isArray(value);

/** Hodnota proti výchozí: stejný druh (text, číslo, ano/ne, pole, objekt), jinak výchozí. */
function merge(fallback: unknown, value: unknown): unknown {
  if (isPlain(fallback)) {
    if (!isPlain(value)) return fallback;
    if (!Object.keys(fallback).length) return value;  // mapa bez pevných klíčů (categoryInfo)
    return Object.fromEntries(Object.entries(fallback).map(([key, inner]) => [key, merge(inner, value[key])]));
  }
  if (Array.isArray(fallback)) return Array.isArray(value) ? value : fallback;
  return typeof value === typeof fallback ? value : fallback;
}

/** Část `settings[key]` doplněná podle výchozího tvaru `empty`. */
export function readPart<T extends object>(settings: Record<string, unknown>, key: string, empty: T): T {
  return merge(empty, settings[key]) as T;
}

export const replaceAt = <T,>(list: T[], index: number, item: T): T[] => list.map((old, at) => at === index ? item : old);
export const removeAt = <T,>(list: T[], index: number): T[] => list.filter((_, at) => at !== index);

/** Posun položky o jedno místo nahoru (-1) nebo dolů (1); na kraji se nic nestane. */
export function moveAt<T>(list: T[], index: number, by: -1 | 1): T[] {
  const target = index + by;
  if (target < 0 || target >= list.length) return list;
  const next = [...list];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

// Stejná pravidla jako server: cesta, kotva, https, mailto, tel; nikdy `javascript:`, `data:` ani `//host`.
const URL = /^(?:\/(?!\/)[^\s<>"'`\\]{0,1999}|#[A-Za-z0-9_-]{0,200}|https:\/\/[^\s<>"'`\\]{3,1990}|mailto:[^\s<>"'`\\]{3,320}|tel:\+?[0-9 ()-]{3,32})$/;
const PAGE_ID = /^[A-Za-z0-9][A-Za-z0-9_:./-]{0,127}$/;
export const HTTPS = /^https:\/\/[^\s<>"'`\\]{3,1990}$/;

export const urlProblem = (url: string): string => !url.trim() || URL.test(url.trim()) ? "" : "Odkaz je /cesta, #kotva, https://, mailto: nebo tel:.";

/** Co odkazu chybí, aby ho server přijal; prázdný text = v pořádku. */
export function linkProblem(link: SiteLink): string {
  if (!link.label.trim()) return "Odkaz potřebuje popisek.";
  if (!!link.pageId.trim() === !!link.url.trim()) return "Vyber stránku, nebo napiš URL (jedno z toho).";
  if (link.pageId.trim() && !PAGE_ID.test(link.pageId.trim())) return "Stránka je id z mapy domény (a-z, 0-9, /, -).";
  return urlProblem(link.url);
}

/** Adresa odkazu v náhledu: URL, nebo cesta stránky; prázdný cíl je kotva. */
export const linkHref = (link: { pageId: string; url: string }): string =>
  link.url.trim() || (link.pageId.trim() ? "/" + link.pageId.trim().replace(/^\/+/, "") : "#");

/** Obrázek pro náhled: asset projektu `assets/<skupina>/<soubor>` z API, https beze změny, jinak nic. */
export function imageSrc(project: string, value: string): string {
  const asset = value.match(/^assets\/([^/]+)\/(.+)$/);
  if (asset) return siteAdminUrls.asset(project, asset[1], asset[2]);
  return HTTPS.test(value) ? value : "";
}
