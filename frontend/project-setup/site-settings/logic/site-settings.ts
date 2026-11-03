// Nastavení webu bez Reactu: které skupiny polí editor ukazuje, s jakým popiskem a stropem znaků
// (stejné stropy drží server v `backend/canvas/site_settings.py`), a čistá změna jednoho pole.
import type { SiteSettings } from "@/shared/types/logic/types";

export type SiteField = { path: string; label: string; max: number; placeholder?: string };
export type SiteGroup = { id: string; title: string; hint: string; fields: SiteField[] };

const typography = (["h1", "h2", "h3", "h4", "h5"] as const).map((key): SiteField => ({
  path: `design.typography.${key}`, label: `Nadpis ${key.toUpperCase()}`, max: 120, placeholder: "písmo, velikost, řez",
}));

export const SITE_GROUPS: SiteGroup[] = [
  { id: "seo", title: "SEO", hint: "Výchozí titulek a popis; stránka je smí přebít.", fields: [
    { path: "seo.titleTemplate", label: "Šablona titulku", max: 120, placeholder: "%s · Název webu" },
    { path: "seo.description", label: "Popis", max: 300 },
    { path: "seo.ogImage", label: "Obrázek pro sdílení", max: 500, placeholder: "/og.png" },
  ] },
  { id: "legal", title: "Právní", hint: "Kontakt pro GDPR a jak web zachází s cookies.", fields: [
    { path: "legal.gdprContact", label: "Kontakt GDPR", max: 200 },
    { path: "legal.cookies", label: "Cookies", max: 300, placeholder: "jen nezbytné" },
  ] },
  { id: "email", title: "E-mail", hint: "Odesílatel formulářů. Heslo SMTP sem nepatří, drží ho server.", fields: [
    { path: "email.from", label: "Odesílatel", max: 200, placeholder: "Web <info@example.cz>" },
    { path: "email.replyTo", label: "Odpovědi na", max: 200 },
  ] },
  { id: "design", title: "Design", hint: "Hlavička a patička platí pro celý web; stránka je smí přebít.", fields: [
    { path: "design.header", label: "Hlavička", max: 300 },
    { path: "design.footer", label: "Patička", max: 300 },
    ...typography,
    { path: "design.typography.body", label: "Text", max: 120 },
    { path: "design.typography.fonts", label: "Písma", max: 200, placeholder: "Fraunces, Inter" },
    { path: "design.buttons", label: "Tlačítka", max: 300 },
  ] },
];

type Tree = { [key: string]: string | Tree };

/** Hodnota pole podle cesty `část.pole` (`design.typography.h1`); chybějící = "". */
export function siteValue(site: SiteSettings, path: string): string {
  const value = path.split(".").reduce<string | Tree | undefined>((node, key) => (typeof node === "object" ? node[key] : undefined), site as unknown as Tree);
  return typeof value === "string" ? value : "";
}

/** Nové nastavení se změněným jedním polem; ostatní větve zůstávají stejné objekty. */
export function withSiteValue(site: SiteSettings, path: string, value: string): SiteSettings {
  const set = (node: Tree, [key, ...rest]: string[]): Tree =>
    ({ ...node, [key]: rest.length ? set((node[key] as Tree) ?? {}, rest) : value });
  return set(site as unknown as Tree, path.split(".")) as unknown as SiteSettings;
}

/** Kolik polí skupiny je vyplněno; editor to ukazuje u sbalené skupiny. */
export const filledCount = (site: SiteSettings, group: SiteGroup) =>
  group.fields.filter((field) => siteValue(site, field.path).trim()).length;
