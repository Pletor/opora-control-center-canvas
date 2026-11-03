# Menu Správy webu

Levé menu stránky Nastavení webové stránky podle `image9.png` (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §1): Nastavení (SEO, Affiliate, E-mail SMTP), Vzhled (Vzhled webu, Hlavička, Patička, Tlačítka, Vlastní fonty), GDPR (Cookie lišta) a Design System (Overview, Colors, Typography, Spacing, Corner radius, Shadows, Components, Assets, Files).

- `logic/site-sections.ts` (+ test): seznam skupin a položek, `ready` = sekce má editor; `readSiteSection` čte sekci z adresy (`siteSection`), neznámá vede na Overview.
- `components/SiteMenu.tsx`: jen zobrazuje; vybranou sekci drží rodič `SiteAdmin` a klik hlásí `onSelect`.

Nový editor (Vzhled, Tlačítka, SEO…) přepne `ready` své položky a v `../components/SitePanel.tsx` doplní svůj dílek.
