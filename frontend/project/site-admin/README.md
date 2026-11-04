# Správa webu

`projectView=site` na stránce Projekt: stránka Nastavení webové stránky podle `image9.png` (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §1 a §3, backend `backend/project/site_admin/`). Jeden dokument na projekt, sdílený všemi doménami.

- **Rodič** `components/SiteAdmin.tsx` drží přes `logic/use-site-admin.ts` uložený a rozepsaný dokument, revizi a uložení: Uložit pošle `PUT /api/site-admin?project=` s `expectedRevision`; 409 = konflikt (uložit moje přes novou revizi, nebo načíst novou a moje zahodit); poznámky serveru (zahozené neplatné hodnoty) se ukážou pod hlavičkou. Drží i vybranou část (`siteSection` v adrese při otevření) a téma náhledu (`data-theme`).
- `components/SitePanel.tsx`: nadpis části a její editor; tady je slot pro každou další část (Vzhled, Tlačítka, SEO…). `components/SiteSaveBar.tsx`: stav a Uložit.
- `logic/site-admin-api.ts` (+ test): adresy, načtení, uložení, `tokens.css`, nahrání fontu. `logic/site-document.ts` (+ test): typy dokumentu a hodnoty per téma. `logic/token-names.ts` (+ test): sdílený jmenný prostor tokenů.
- Dílky: `site-menu/` (levé menu), `site-appearance/` (Vzhled webu), `site-buttons/` (Tlačítka webu), `site-fields/` (společná pole obou), `ds-preview/` (`tokens.css` a `components.css` uzavřené do náhledu), `ds-overview/`, `ds-colors/`, `ds-typography/`, `ds-scale/` (Spacing, Corner radius, Shadows), `ds-files/`, `site-proposals/` (pruh „Srdce navrhuje změnu“: rozdíl, Přijmout / Zamítnout; přijetí zapíše a rodič dokument načte znovu).

Hotové jsou Vzhled webu, Tlačítka webu, části Design Systemu (Overview, Colors, Typography, Spacing, Corner radius, Shadows, Files) a Vlastní fonty (= Typography). Odmítnuté vlastní CSS (422) drží rodič jako `invalid` a editor ho ukáže na řádku; `components.css` načítá rodič spolu s `tokens.css` po každém uložení. Ostatní položky menu ukážou „v dalším kroku“.

Vstupy: karta „Design systém webu“ na stránce projektu (`project-setup/site-design-card/`) a akce „Správa webu“ na kartě webové domény v landingu architektury. Otevření vyřizuje App.
