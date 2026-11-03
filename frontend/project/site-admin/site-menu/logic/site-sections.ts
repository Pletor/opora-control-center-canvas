// Levé menu stránky Nastavení webové stránky podle `image9.png` (kontrakt Správy webu §1): tři skupiny nastavení
// webu a vedle nich Design System. Položka bez editoru (`ready: false`) se ukáže, ale otevře jen „v dalším kroku“;
// editor do ní přidá jiné PR tím, že tu přepne `ready` a v `SitePanel` doplní svůj dílek.

export type SiteSection =
  | "seo" | "affiliate" | "email"
  | "appearance" | "header" | "footer" | "buttons" | "fonts"
  | "cookies"
  | "overview" | "colors" | "typography" | "spacing" | "radius" | "shadow" | "components" | "assets" | "files";

export type SiteMenuItem = { id: SiteSection; label: string; ready: boolean };
export type SiteMenuGroup = { id: string; label: string; items: SiteMenuItem[] };

const item = (id: SiteSection, label: string, ready = false): SiteMenuItem => ({ id, label, ready });

export const SITE_MENU: SiteMenuGroup[] = [
  { id: "settings", label: "Nastavení", items: [item("seo", "SEO"), item("affiliate", "Affiliate"), item("email", "E-mail (SMTP)")] },
  { id: "appearance", label: "Vzhled", items: [item("appearance", "Vzhled webu", true), item("header", "Hlavička webu"), item("footer", "Patička webu"),
    item("buttons", "Tlačítka webu", true), item("fonts", "Vlastní fonty", true)] },
  { id: "gdpr", label: "GDPR", items: [item("cookies", "Cookie lišta")] },
  { id: "design", label: "Design System", items: [item("overview", "Overview", true), item("colors", "Colors", true),
    item("typography", "Typography", true), item("spacing", "Spacing", true), item("radius", "Corner radius", true),
    item("shadow", "Shadows", true), item("components", "Components"), item("assets", "Assets"), item("files", "Files", true)] },
];

const ALL = SITE_MENU.flatMap((group) => group.items);

/** Sekce z adresy (`siteSection`); neznámá nebo chybějící vede na Overview design systému. */
export function readSiteSection(value: string | null): SiteSection {
  return ALL.find((entry) => entry.id === value)?.id ?? "overview";
}

export const siteMenuItem = (id: SiteSection): SiteMenuItem => ALL.find((entry) => entry.id === id) ?? ALL[0];
