// Hlavička webu `settings.header` (backend `backend/project/site_admin/site_chrome.py`): logo z Assets, menu ze
// stránek mapy domény (`source:pages`) nebo ruční, CTA tlačítko varianty z Tlačítek webu, přilepení a varianta.
// Styl `.ds-header` je v `components.css`; náhled skládá markup stejně, jak ho popisuje README pro dělníka.
import { EMPTY_LINK, linkHref, readPart, type SiteLink } from "@/project/site-admin/site-fields/logic/settings-part";

export type HeaderVariant = "classic" | "centered" | "minimal";
export type Header = {
  logoAsset: string; logoAlt: string; nav: "source:pages" | "manual"; items: SiteLink[];
  cta: SiteLink & { variant: string }; sticky: boolean; variant: HeaderVariant;
};

export const EMPTY_HEADER: Header = {
  logoAsset: "", logoAlt: "", nav: "source:pages", items: [], cta: { ...EMPTY_LINK, variant: "" }, sticky: false, variant: "classic",
};
export const MAX_ITEMS = 12;
/** Zástupné hlavní stránky pro náhled menu `source:pages`; skutečné čte dělník z mapy domény. */
export const SAMPLE_PAGES: SiteLink[] = ["Úvod", "Služby", "O nás", "Kontakt"].map((label, index) =>
  ({ label, pageId: index ? label.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\s+/g, "-") : "uvod", url: "" }));

export const readHeader = (settings: Record<string, unknown>): Header => readPart(settings, "header", EMPTY_HEADER);

/** Odkazy menu v náhledu: u `source:pages` zástupné stránky mapy a za nimi ruční odkazy navíc. */
export const navItems = (header: Header): SiteLink[] =>
  (header.nav === "source:pages" ? [...SAMPLE_PAGES, ...header.items] : header.items).filter((item) => item.label.trim());

/** Třídy hlavičky podle nastavení (BEM modifikátory z `components.css`). */
export const headerClass = (header: Header): string =>
  ["ds-header", `ds-header--${header.variant}`, ...(header.sticky ? ["ds-header--sticky"] : [])].join(" ");

/** CTA v náhledu: třída varianty (zvolená, jinak první), adresa a jestli se má vůbec ukázat. */
export function ctaView(header: Header, variants: string[]): { show: boolean; className: string; href: string } {
  const variant = header.cta.variant && variants.includes(header.cta.variant) ? header.cta.variant : variants[0] ?? "";
  return { show: !!header.cta.label.trim(), className: "ds-btn ds-btn--sm" + (variant ? ` ds-btn--${variant}` : ""), href: linkHref(header.cta) };
}

/** Co CTA chybí, aby ho server přijal. */
export function ctaProblem(header: Header): string {
  const { label, pageId, url } = header.cta;
  if (pageId.trim() && url.trim()) return "CTA míří buď na stránku, nebo na URL.";
  return label.trim() && !pageId.trim() && !url.trim() ? "CTA potřebuje cíl (stránku nebo URL)." : "";
}
